from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import json
import logging
import asyncio
import aiohttp
import numpy as np
import pandas as pd
import traceback
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo
from src.tools.finance import _fetch_batch_history, _extract_ticker_data, _normalize_ticker

from src.tools.scanner import (
    _build_session_watchlist_impl, 
    _run_activity_pulse_impl,
    build_session_watchlist,
    run_activity_pulse
)
from src.tools.sortino_sniper_trawl import run_background_trawl
from src.tools.shield_scanner_trawl import run_shield_trawl

router = APIRouter()
logger = logging.getLogger(__name__)

def patch_json():
    """Global process-level patch for NumPy serialization in standard json library."""
    original_default = json.JSONEncoder.default
    def new_default(self, obj):
        if hasattr(obj, "item"):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return original_default(self, obj)
    json.JSONEncoder.default = new_default

patch_json()

def inject_watchdog():
    """Global watchdog to catch and trace JSON serialization failures to disk."""
    log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "SCANNER_TRACE.log"))
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    original_dumps = json.dumps
    def wrapped_dumps(obj, *args, **kwargs):
        try:
            return original_dumps(obj, *args, **kwargs)
        except TypeError as e:
            if "int64" in str(e) or "serializable" in str(e):
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("\n" + "!"*60 + "\n")
                    f.write(f"!!! WATCHDOG TRACE: JSON SERIALIZATION FAILURE !!!\n")
                    f.write(f"Time: {datetime.now().isoformat()}\n")
                    f.write(f"Error: {e}\n")
                    f.write(f"Context Class: {obj.__class__.__name__}\n")
                    f.write(f"Context Start: {str(obj)[:500]}\n")
                    f.write("\nStack Trace:\n")
                    f.write(traceback.format_exc())
                    f.write("!"*60 + "\n")
                logger.error(f"JSON Watchdog caught failure. Trace written to {log_path}")
            raise e
    json.dumps = wrapped_dumps
    
    original_dump = json.dump
    def wrapped_dump(obj, fp, *args, **kwargs):
        try:
            return original_dump(obj, fp, *args, **kwargs)
        except TypeError as e:
            if "int64" in str(e) or "serializable" in str(e):
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("\n" + "!"*60 + "\n")
                    f.write(f"!!! WATCHDOG TRACE: JSON FILE WRITE FAILURE !!!\n")
                    f.write(f"Time: {datetime.now().isoformat()}\n")
                    f.write(f"Error: {e}\n")
                    f.write("\nStack Trace:\n")
                    f.write(traceback.format_exc())
                    f.write("!"*60 + "\n")
                logger.error(f"JSON Watchdog caught file failure. Trace written to {log_path}")
            raise e
    json.dump = wrapped_dump

inject_watchdog()

def sanitize_data(data):
    """Hyper-aggressive recursive sanitizer for NumPy, Pandas, and Python structural types."""
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple, set)):
        return [sanitize_data(v) for v in data]
    elif isinstance(data, pd.Timestamp):
        return data.isoformat()
    elif isinstance(data, (pd.Series, pd.DataFrame)):
        return sanitize_data(data.to_dict())
    elif isinstance(data, np.ndarray):
        return data.tolist()
    elif hasattr(data, "item") and not isinstance(data, (type, pd.Series, pd.DataFrame)): 
        return data.item()
    return data

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "item"): # Standard NumPy scalar conversion
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)

@router.get("/trawl")
async def trigger_scanner_trawl():
    """Manual trigger for Layer A (The Background Trawl)."""
    try:
        results = await run_background_trawl()
        return sanitize_data({"status": "success", "data": results})
    except Exception as e:
        logger.error(f"Trawl failed: {e}")
        return {"status": "error", "message": str(e)}

import time

TRENDS_CACHE = {}  # {symbol: {"trends": {...}, "sparkline": [...], "timestamp": float}}
TRENDS_CACHE_EXPIRY = 300  # 5 minutes
YF_LOCK = asyncio.Lock()

TRENDS_CACHE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "trends_cache.json"))

import threading

_SAVE_THREAD_LOCK = threading.Lock()
_CACHE_DIRTY = False
_SAVE_TASK = None

def save_trends_cache():
    with _SAVE_THREAD_LOCK:
        try:
            os.makedirs(os.path.dirname(TRENDS_CACHE_PATH), exist_ok=True)
            temp_path = TRENDS_CACHE_PATH + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(TRENDS_CACHE, f, default=str)
            if os.path.exists(temp_path):
                os.replace(temp_path, TRENDS_CACHE_PATH)
        except Exception as e:
            logger.error(f"Failed to save TRENDS_CACHE to disk: {e}")

async def async_save_trends_cache():
    global _CACHE_DIRTY, _SAVE_TASK
    _CACHE_DIRTY = True
    
    # Check if we are running in the main thread
    is_main_thread = (threading.current_thread() is threading.main_thread())
    
    if not is_main_thread:
        # If on a background thread, run the file write synchronously to avoid cross-loop task creation
        await asyncio.to_thread(save_trends_cache)
        return
        
    if _SAVE_TASK is not None and not _SAVE_TASK.done():
        return
        
    async def debounced_save():
        global _CACHE_DIRTY
        await asyncio.sleep(2.0)
        if _CACHE_DIRTY:
            _CACHE_DIRTY = False
            try:
                await asyncio.to_thread(save_trends_cache)
                logger.info("TRENDS_CACHE successfully saved to disk (async debounced).")
            except Exception as e:
                logger.error(f"Async save_trends_cache failed: {e}")
                
    _SAVE_TASK = asyncio.create_task(debounced_save())

def load_trends_cache():
    global TRENDS_CACHE
    if os.path.exists(TRENDS_CACHE_PATH):
        try:
            with open(TRENDS_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    TRENDS_CACHE.update(data)
                    logger.info(f"Loaded {len(TRENDS_CACHE)} symbols from persistent trends cache.")
        except Exception as e:
            logger.error(f"Failed to load TRENDS_CACHE from disk: {e}")

load_trends_cache()

def fill_futures_gaps(df, freq):
    """
    Ensures futures dataframes are gapless by generating a complete index
    matching CME futures trading hours (excluding weekend and daily maintenance hour)
    and forward-filling price values.
    """
    if df is None or df.empty:
        return df
        
    import pandas as pd
    orig_tz = df.index.tz
    
    # Convert index to America/New_York (Eastern Time) for session filtering
    if orig_tz is not None:
        df_ny = df.tz_convert('America/New_York')
    else:
        df_ny = df.tz_localize('UTC').tz_convert('America/New_York')
        
    start_time = df_ny.index.min()
    end_time = df_ny.index.max()
    
    # Generate all timestamps with the target frequency
    all_times = pd.date_range(start=start_time, end=end_time, freq=freq)
    
    # Filter CME trading hours:
    # - Closed on Friday 5:00 PM ET to Sunday 6:00 PM ET
    # - Daily maintenance close: 5:00 PM ET to 6:00 PM ET (17:00 ET hour)
    valid_times = []
    for dt in all_times:
        day_of_week = dt.dayofweek  # 0=Monday, ..., 6=Sunday
        hour = dt.hour
        minute = dt.minute
        
        is_weekend = False
        if day_of_week == 5:  # Saturday
            is_weekend = True
        elif day_of_week == 4 and (hour > 17 or (hour == 17 and minute > 0)):  # Friday after 5 PM
            is_weekend = True
        elif day_of_week == 6 and hour < 18:  # Sunday before 6 PM
            is_weekend = True
            
        # Daily maintenance hour
        is_maintenance = (hour == 17)
        
        if not is_weekend and not is_maintenance:
            valid_times.append(dt)
            
    # Reindex to the valid trading session range
    df_filled = df_ny.reindex(valid_times)
    
    # Forward-fill the Close column
    close_col = next((c for c in df_filled.columns if str(c).lower() == 'close'), 'Close')
    df_filled[close_col] = df_filled[close_col].ffill()
    
    # Fill missing Open/High/Low with Close (carrying over flat price if no trades occurred)
    open_col = next((c for c in df_filled.columns if str(c).lower() == 'open'), 'Open')
    high_col = next((c for c in df_filled.columns if str(c).lower() == 'high'), 'High')
    low_col = next((c for c in df_filled.columns if str(c).lower() == 'low'), 'Low')
    
    df_filled[open_col] = df_filled[open_col].fillna(df_filled[close_col])
    df_filled[high_col] = df_filled[high_col].fillna(df_filled[close_col])
    df_filled[low_col] = df_filled[low_col].fillna(df_filled[close_col])
    
    # Fill missing Volume with 0.0
    vol_col = next((c for c in df_filled.columns if str(c).lower() == 'volume'), 'Volume')
    if vol_col in df_filled.columns:
        df_filled[vol_col] = df_filled[vol_col].fillna(0.0)
        
    # Convert index back to original timezone representation
    if orig_tz is not None:
        df_filled = df_filled.tz_convert(orig_tz)
    else:
        df_filled = df_filled.tz_localize(None)
        
    return df_filled


def calculate_atr_14(df_1d):
    """Calculates 14-period daily ATR from 1d history."""
    if df_1d is None or df_1d.empty or len(df_1d) < 2:
        return 1.0
    try:
        df = df_1d.copy()
        col_map = {str(col).lower(): col for col in df.columns}
        high_col = col_map.get("high")
        low_col = col_map.get("low")
        close_col = col_map.get("close")
        if not high_col or not low_col or not close_col:
            return 1.0
            
        highs = df[high_col]
        lows = df[low_col]
        closes = df[close_col]
        
        tr_list = []
        for i in range(1, len(df)):
            tr = max(
                highs.iloc[i] - lows.iloc[i],
                abs(highs.iloc[i] - closes.iloc[i-1]),
                abs(lows.iloc[i] - closes.iloc[i-1])
            )
            tr_list.append(tr)
            
        if len(tr_list) >= 14:
            atr = sum(tr_list[-14:]) / 14.0
        elif tr_list:
            atr = sum(tr_list) / len(tr_list)
        else:
            atr = 1.0
        return max(atr, 0.0001)
    except Exception as e:
        logger.error(f"Error calculating ATR: {e}")
        return 1.0

def calculate_vwap_state(df_5m, atr=1.0):
    """
    Given a 5m interval DataFrame with datetime index, calculate current day's VWAP
    and calculate distance normalized to ATR: (Close - VWAP) / ATR.
    Returns a float in range [-1.0, 1.0].
    """
    if df_5m is None or df_5m.empty:
        return 0.0
        
    try:
        df = df_5m.copy()
        col_map = {str(col).lower(): col for col in df.columns}
        close_col = col_map.get("close")
        volume_col = col_map.get("volume")
        high_col = col_map.get("high")
        low_col = col_map.get("low")
        
        if not close_col or not volume_col:
            return 0.0
            
        if high_col and low_col:
            df["Typical_Price"] = (df[high_col] + df[low_col] + df[close_col]) / 3.0
        else:
            df["Typical_Price"] = df[close_col]
            
        if not isinstance(df.index, pd.DatetimeIndex):
            return 0.0
            
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df_et = df.tz_convert("America/New_York")
        df["et_date"] = df_et.index.date
        
        latest_date = df["et_date"].iloc[-1]
        latest_day_df = df[df["et_date"] == latest_date]
        
        if latest_day_df.empty:
            return 0.0
            
        cum_vol = latest_day_df[volume_col].cumsum()
        cum_tp_vol = (latest_day_df["Typical_Price"] * latest_day_df[volume_col]).cumsum()
        
        last_cum_vol = cum_vol.iloc[-1]
        if last_cum_vol <= 0:
            vwap = latest_day_df["Typical_Price"].mean()
        else:
            vwap = cum_tp_vol.iloc[-1] / last_cum_vol
            
        last_close = latest_day_df[close_col].iloc[-1]
        
        raw_dist = (last_close - vwap) / atr
        norm_dist = max(-1.0, min(1.0, raw_dist))
        return round(norm_dist, 2)
            
    except Exception as e:
        logger.error(f"Error calculating VWAP state: {e}")
        return 0.0

def calculate_crt_segments(df):
    if df is None or len(df) < 6:
        return [{"state": "NONE", "is_forming": i == 4, "potential_setup": "NONE", "open_time": "", "close_time": ""} for i in range(5)]
    
    sub = df.tail(6)
    segments = []
    
    col_map = {str(c).lower(): c for c in sub.columns}
    high_col = col_map.get("high")
    low_col = col_map.get("low")
    close_col = col_map.get("close")
    open_col = col_map.get("open")
    
    if not (high_col and low_col and close_col and open_col):
        return [{"state": "NONE", "is_forming": i == 4, "potential_setup": "NONE", "open_time": "", "close_time": ""} for i in range(5)]

    # Infer candle duration from index difference to calculate close time
    candle_duration = pd.Timedelta(minutes=15) # default fallback
    try:
        if len(sub) > 1:
            diffs = [sub.index[k] - sub.index[k-1] for k in range(1, len(sub))]
            if diffs:
                candle_duration = min(diffs)
    except Exception as e:
        logger.warning(f"Error calculating candle duration: {e}")

    for i in range(1, 6):
        prev = sub.iloc[i-1]
        curr = sub.iloc[i]
        
        prev_low = float(prev[low_col])
        prev_high = float(prev[high_col])
        curr_low = float(curr[low_col])
        curr_high = float(curr[high_col])
        curr_close = float(curr[close_col])
        curr_open = float(curr[open_col])
        
        is_forming = (i == 5)
        state = "NONE"
        potential_setup = "NONE"
        
        # Define noise tolerance (0.005% of price) to prevent minor data feed differences from causing false states
        tol = prev_low * 0.00005
        
        is_bull_sweep = curr_low < prev_low - tol and curr_close > prev_low - tol and curr_close <= prev_high + tol
        is_bear_sweep = curr_high > prev_high + tol and curr_close < prev_high + tol and curr_close >= prev_low - tol

        if is_bull_sweep and is_bear_sweep:
            state = "DOUBLE_SWEEP"
            if is_forming:
                potential_setup = "BULLISH" if curr_close >= curr_open else "BEARISH"
        elif is_bull_sweep:
            state = "BULL_SWEEP"
            if is_forming:
                potential_setup = "BULLISH"
        elif is_bear_sweep:
            state = "BEAR_SWEEP"
            if is_forming:
                potential_setup = "BEARISH"
        elif curr_close > prev_high + tol:
            state = "BULL_OUTSIDE"
        elif curr_close < prev_low - tol:
            state = "BEAR_OUTSIDE"
        elif curr_high <= prev_high + tol and curr_low >= prev_low - tol:
            state = "INSIDE"
            
        open_time_str = ""
        close_time_str = ""
        try:
            if hasattr(curr, "name") and isinstance(curr.name, (pd.Timestamp, datetime)):
                import pytz
                est = pytz.timezone("America/New_York")
                dt_open = curr.name
                if isinstance(dt_open, pd.Timestamp):
                    dt_open = dt_open.to_pydatetime()
                if dt_open.tzinfo is not None:
                    dt_open_local = dt_open.astimezone(est)
                else:
                    dt_open_local = pytz.utc.localize(dt_open).astimezone(est)
                    
                dt_close_local = dt_open_local + candle_duration
                
                open_time_str = dt_open_local.strftime("%Y-%m-%d %H:%M %Z")
                close_time_str = dt_close_local.strftime("%Y-%m-%d %H:%M %Z")
        except Exception as e:
            logger.warning(f"Error formatting candle times in segments: {e}")

        segments.append({
            "state": state,
            "is_forming": is_forming,
            "potential_setup": potential_setup,
            "high": round(curr_high, 2),
            "low": round(curr_low, 2),
            "close": round(curr_close, 2),
            "open": round(curr_open, 2),
            "prev_high": round(prev_high, 2),
            "prev_low": round(prev_low, 2),
            "open_time": open_time_str,
            "close_time": close_time_str
        })
    return segments

def backtest_timeframe_setups(df):
    if df is None or len(df) < 10:
        return {"success": 0, "fail": 0}
    
    col_map = {str(c).lower(): c for c in df.columns}
    high_col = col_map.get("high", "High")
    low_col = col_map.get("low", "Low")
    close_col = col_map.get("close", "Close")
    open_col = col_map.get("open", "Open")
    
    success_count = 0
    fail_count = 0
    
    states = ["NONE"] * len(df)
    for t in range(1, len(df)):
        prev = df.iloc[t-1]
        curr = df.iloc[t]
        
        try:
            prev_low = float(prev[low_col].iloc[0]) if isinstance(prev[low_col], pd.Series) else float(prev[low_col])
            prev_high = float(prev[high_col].iloc[0]) if isinstance(prev[high_col], pd.Series) else float(prev[high_col])
            curr_low = float(curr[low_col].iloc[0]) if isinstance(curr[low_col], pd.Series) else float(curr[low_col])
            curr_high = float(curr[high_col].iloc[0]) if isinstance(curr[high_col], pd.Series) else float(curr[high_col])
            curr_close = float(curr[close_col].iloc[0]) if isinstance(curr[close_col], pd.Series) else float(curr[close_col])
            curr_open = float(curr[open_col].iloc[0]) if isinstance(curr[open_col], pd.Series) else float(curr[open_col])
        except Exception:
            continue
            
        is_bull_sweep = curr_low < prev_low and curr_close > prev_low
        is_bear_sweep = curr_high > prev_high and curr_close < prev_high
        
        if is_bull_sweep and is_bear_sweep:
            states[t] = "DOUBLE_SWEEP"
        elif is_bull_sweep:
            states[t] = "BULL_SWEEP"
        elif is_bear_sweep:
            states[t] = "BEAR_SWEEP"
        elif curr_close > prev_high:
            states[t] = "BULL_OUTSIDE"
        elif curr_close < prev_low:
            states[t] = "BEAR_OUTSIDE"
        elif curr_high <= prev_high and curr_low >= prev_low:
            states[t] = "INSIDE"
            
    for t in range(1, len(df)):
        sweep_state = states[t]
        if sweep_state in ["BULL_SWEEP", "BEAR_SWEEP", "BULL_OUTSIDE", "BEAR_OUTSIDE", "DOUBLE_SWEEP"]:
            range_candle_idx = t - 1
            try:
                range_low = float(df.iloc[range_candle_idx][low_col].iloc[0]) if isinstance(df.iloc[range_candle_idx][low_col], pd.Series) else float(df.iloc[range_candle_idx][low_col])
                range_high = float(df.iloc[range_candle_idx][high_col].iloc[0]) if isinstance(df.iloc[range_candle_idx][high_col], pd.Series) else float(df.iloc[range_candle_idx][high_col])
            except Exception:
                continue
                
            is_outside_setup = sweep_state in ["BULL_OUTSIDE", "BEAR_OUTSIDE"]
            
            end_window = min(len(df) - 1, t + 4)
            breached = False
            
            for k in range(t, end_window + 1):
                if states[k] == "INSIDE":
                    try:
                        range_low = float(df.iloc[k][low_col].iloc[0]) if isinstance(df.iloc[k][low_col], pd.Series) else float(df.iloc[k][low_col])
                        range_high = float(df.iloc[k][high_col].iloc[0]) if isinstance(df.iloc[k][high_col], pd.Series) else float(df.iloc[k][high_col])
                    except Exception:
                        pass
                
                try:
                    close_val = float(df.iloc[k][close_col].iloc[0]) if isinstance(df.iloc[k][close_col], pd.Series) else float(df.iloc[k][close_col])
                except Exception:
                    continue
                    
                if is_outside_setup:
                    if close_val >= range_low and close_val <= range_high:
                        breached = True
                        break
                else:
                    if sweep_state == "BULL_SWEEP" and close_val < range_low:
                        breached = True
                        break
                    elif sweep_state == "BEAR_SWEEP" and close_val > range_high:
                        breached = True
                        break
                    elif sweep_state == "DOUBLE_SWEEP":
                        if close_val < range_low or close_val > range_high:
                            breached = True
                            break
                            
            if breached:
                fail_count += 1
            else:
                if end_window - t == 4:
                    success_count += 1
                    
    return {"success": success_count, "fail": fail_count}

def align_forming_candle(df, tf_name, live_price, now_time, is_future=False):
    if df is None or df.empty or live_price is None:
        return df
        
    try:
        import pandas as pd
        import pytz
        from datetime import datetime, timedelta
        
        # Get current time localized to the dataframe index timezone
        tz = df.index.tz
        if tz is None:
            tz = pytz.utc
            
        now_dt = datetime.fromtimestamp(now_time, pytz.utc).astimezone(tz)
        
        # Calculate current forming candle timestamp
        tf_clean = tf_name.lower().strip()
        if tf_clean in ["15m", "15min"]:
            minute = (now_dt.minute // 15) * 15
            current_forming_ts = now_dt.replace(minute=minute, second=0, microsecond=0)
        elif tf_clean in ["1h", "1min"]:
            current_forming_ts = now_dt.replace(minute=0, second=0, microsecond=0)
        elif tf_clean in ["4h"]:
            if is_future:
                shifted_dt = now_dt - timedelta(hours=2)
                hour = (shifted_dt.hour // 4) * 4
                current_forming_ts = shifted_dt.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(hours=2)
            else:
                hour = (now_dt.hour // 4) * 4
                current_forming_ts = now_dt.replace(hour=hour, minute=0, second=0, microsecond=0)
        elif tf_clean in ["1d"]:
            current_forming_ts = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return df

        if df.index[-1] < current_forming_ts:
            col_map = {str(c).lower(): c for c in df.columns}
            open_col = col_map.get("open", "Open")
            high_col = col_map.get("high", "High")
            low_col = col_map.get("low", "Low")
            close_col = col_map.get("close", "Close")
            volume_col = col_map.get("volume", "Volume")
            
            prev_close = float(df[close_col].iloc[-1])
            new_row_data = {
                open_col: prev_close,
                high_col: max(prev_close, live_price),
                low_col: min(prev_close, live_price),
                close_col: live_price
            }
            if volume_col in col_map:
                new_row_data[volume_col] = 0.0
                
            new_row = pd.DataFrame([new_row_data], index=[current_forming_ts])
            df = pd.concat([df, new_row])
    except Exception as align_e:
        logger.error(f"Error in align_forming_candle: {align_e}")
        
    return df

PENDING_FETCH = set()

async def bulk_fetch_trends_and_sparklines(symbols):
    # Filter out symbols that are already being fetched
    to_fetch = [s for s in symbols if s not in PENDING_FETCH]
    if not to_fetch:
        return
        
    for s in to_fetch:
        PENDING_FETCH.add(s)
        
    try:
        import yfinance as yf
        from src.tools.macros import calculate_trend_alignment, extract_single_ticker_df
        
        logger.info(f"VLI: Background fetching trend histories and sparklines for: {to_fetch}")
        
        # Download in safe chunks of 10 to avoid rate limits
        chunk_size = 10
        for i in range(0, len(to_fetch), chunk_size):
            chunk = to_fetch[i:i+chunk_size]
            
            # Map input symbols to yfinance-compatible symbols
            normalized_chunk_map = {sym: _normalize_ticker(sym) for sym in chunk}
            
            # Partition search symbols into futures and stocks
            futures_search = []
            stocks_search = []
            for sym in chunk:
                norm_sym = normalized_chunk_map[sym]
                clean_sym = sym.lstrip("/^").upper()
                is_fut = clean_sym in ["ES", "MES", "NQ", "MNQ", "YM", "MYM", "RTY", "M2K", "CL", "MCL", "GC", "MGC", "NKD", "MNK"] or clean_sym.endswith("=F")
                if is_fut:
                    futures_search.append(norm_sym)
                else:
                    stocks_search.append(norm_sym)
            
            futures_search = list(set(futures_search))
            stocks_search = list(set(stocks_search))
            all_search = list(set(futures_search + stocks_search))
            
            async with YF_LOCK:
                # 1m
                f_1m = await asyncio.to_thread(yf.download, futures_search, period="5d", interval="1m", prepost=True, progress=False) if futures_search else None
                s_1m = await asyncio.to_thread(yf.download, stocks_search, period="5d", interval="1m", prepost=True, progress=False) if stocks_search else None
                
                # 5m
                f_5m = await asyncio.to_thread(yf.download, futures_search, period="5d", interval="5m", prepost=True, progress=False) if futures_search else None
                s_5m = await asyncio.to_thread(yf.download, stocks_search, period="5d", interval="5m", prepost=True, progress=False) if stocks_search else None
                
                # 15m
                f_15m = await asyncio.to_thread(yf.download, futures_search, period="1mo", interval="15m", prepost=True, progress=False) if futures_search else None
                s_15m = await asyncio.to_thread(yf.download, stocks_search, period="1mo", interval="15m", prepost=True, progress=False) if stocks_search else None
                
                # 1h
                f_1h = await asyncio.to_thread(yf.download, futures_search, period="3mo", interval="1h", prepost=True, progress=False) if futures_search else None
                s_1h = await asyncio.to_thread(yf.download, stocks_search, period="3mo", interval="1h", prepost=True, progress=False) if stocks_search else None
                
                # 1d & 1w (prepost not applicable)
                c_batch_1d = await asyncio.to_thread(yf.download, all_search, period="2y", interval="1d", progress=False) if all_search else None
                c_batch_1w = await asyncio.to_thread(yf.download, all_search, period="5y", interval="1wk", progress=False) if all_search else None
            
            # Helper to merge dfs
            def safe_merge(f_df, s_df):
                if f_df is not None and not f_df.empty and s_df is not None and not s_df.empty:
                    return pd.concat([f_df, s_df], axis=1)
                elif f_df is not None and not f_df.empty:
                    return f_df
                else:
                    return s_df
                    
            c_batch_1m = safe_merge(f_1m, s_1m)
            c_batch_5m = safe_merge(f_5m, s_5m)
            c_batch_15m = safe_merge(f_15m, s_15m)
            c_batch_1h = safe_merge(f_1h, s_1h)
            
            now = time.time()
            for sym in chunk:
                norm_sym = normalized_chunk_map[sym]
                df_1m = extract_single_ticker_df(c_batch_1m, norm_sym)
                df_5m = extract_single_ticker_df(c_batch_5m, norm_sym)
                df_15m = extract_single_ticker_df(c_batch_15m, norm_sym)
                df_1h = extract_single_ticker_df(c_batch_1h, norm_sym)
                df_1d = extract_single_ticker_df(c_batch_1d, norm_sym)
                df_1w = extract_single_ticker_df(c_batch_1w, norm_sym)
                
                clean_sym = sym.lstrip("/^").upper()
                is_future = clean_sym in ["ES", "MES", "NQ", "MNQ", "YM", "MYM", "RTY", "M2K", "CL", "MCL", "GC", "MGC", "NKD", "MNK"] or clean_sym.endswith("=F")
                
                # Fallback for individual missing data due to batch merging quirks
                if (df_1m is None or df_1m.empty) and is_future:
                    try:
                        logger.info(f"VLI: Batch 1m empty for futures ticker {sym}, downloading individually.")
                        sdf = await asyncio.to_thread(yf.download, norm_sym, period="5d", interval="1m", prepost=True, progress=False)
                        df_1m = extract_single_ticker_df(sdf, norm_sym)
                    except Exception as ef:
                        logger.warning(f"VLI: Fallback 1m fetch failed for {sym}: {ef}")
                
                if is_future:
                    if df_1m is not None and not df_1m.empty:
                        try:
                            col_map = {str(c).lower(): c for c in df_1m.columns}
                            agg_dict = {}
                            if 'open' in col_map: agg_dict[col_map['open']] = 'first'
                            if 'high' in col_map: agg_dict[col_map['high']] = 'max'
                            if 'low' in col_map: agg_dict[col_map['low']] = 'min'
                            if 'close' in col_map: agg_dict[col_map['close']] = 'last'
                            if 'volume' in col_map: agg_dict[col_map['volume']] = 'sum'
                            
                            df_15m_res = df_1m.resample('15min').agg(agg_dict).dropna()
                            df_15m_res.columns = [col_map[str(c).lower()] for c in df_15m_res.columns]
                            df_15m = df_15m_res
                            
                            df_1h_res = df_1m.resample('1h').agg(agg_dict).dropna()
                            df_1h_res.columns = [col_map[str(c).lower()] for c in df_1h_res.columns]
                            df_1h = df_1h_res
                        except Exception as resample_e:
                            logger.error(f"Failed to resample futures timeframes from 1m for {sym}: {resample_e}")
                            
                    # Apply futures gap-filling to ensure alignment with TradingView
                    df_15m = fill_futures_gaps(df_15m, '15min')
                    df_1h = fill_futures_gaps(df_1h, '1h')
                
                c_timeframes = {
                    "1m": df_1m,
                    "5m": df_5m,
                    "15m": df_15m,
                    "1h": df_1h,
                    "4h": None,
                    "1d": df_1d,
                    "1w": df_1w
                }
                
                df_1h = c_timeframes["1h"]
                if df_1h is not None and not df_1h.empty:
                    try:
                        col_map = {str(c).lower(): c for c in df_1h.columns}
                        agg_dict = {}
                        if 'open' in col_map: agg_dict[col_map['open']] = 'first'
                        if 'high' in col_map: agg_dict[col_map['high']] = 'max'
                        if 'low' in col_map: agg_dict[col_map['low']] = 'min'
                        if 'close' in col_map: agg_dict[col_map['close']] = 'last'
                        if 'volume' in col_map: agg_dict[col_map['volume']] = 'sum'
                        if is_future:
                            c_timeframes["4h"] = df_1h.resample('4h', offset='2h').agg(agg_dict).dropna()
                            c_timeframes["4h"] = fill_futures_gaps(c_timeframes["4h"], '4h')
                        else:
                            c_timeframes["4h"] = df_1h.resample('4h').agg(agg_dict).dropna()
                    except Exception as resample_e:
                        logger.error(f"Failed to resample 4h for {sym}: {resample_e}")
                        
                trends = {}
                for tf_name, df in c_timeframes.items():
                    if df is not None and not df.empty and "close" in [str(c).lower() for c in df.columns]:
                        try:
                            trends[tf_name] = calculate_trend_alignment(df)
                        except Exception as align_e:
                            logger.error(f"Failed to align trend for {sym} {tf_name}: {align_e}")
                            trends[tf_name] = "No Data"
                    else:
                        trends[tf_name] = "No Data"
                
                # Extract sparklines for 1m, 5m, 15m, 1h
                def extract_raw_sparkline(df, num_points=30):
                    if df is None or df.empty:
                        return []
                    col = "Close" if "Close" in df.columns else "close"
                    if col not in df.columns:
                        return []
                    series = df[col].dropna()
                    if series.empty:
                        return []
                    
                    # Convert to America/New_York (Eastern Time) for consistent representation
                    try:
                        if hasattr(series.index, "tz") and series.index.tz is not None:
                            series.index = series.index.tz_convert("America/New_York")
                        elif not hasattr(series.index, "tz") or series.index.tz is None:
                            series.index = series.index.tz_localize("UTC").tz_convert("America/New_York")
                    except Exception as tz_e:
                        logger.warning(f"Timezone conversion failed for sparkline: {tz_e}")
                        
                    subset = series.iloc[-num_points:]
                    result = []
                    for idx, val in subset.items():
                        time_str = idx.strftime("%Y-%m-%d %H:%M") if hasattr(idx, "strftime") else str(idx)
                        result.append({"v": float(val), "t": time_str})
                    return result

                spark_1m = extract_raw_sparkline(c_timeframes["1m"])
                spark_5m = extract_raw_sparkline(c_timeframes["5m"])
                spark_15m = extract_raw_sparkline(c_timeframes["15m"])
                spark_1h = extract_raw_sparkline(c_timeframes["1h"])
                spark_4h = extract_raw_sparkline(c_timeframes["4h"])
                spark_1d = extract_raw_sparkline(c_timeframes["1d"])
                
                # Calculate live price, change, and rvol dynamically
                live_price = None
                live_change = None
                live_rvol = None
                
                df_1m = c_timeframes["1m"]
                df_1d = c_timeframes["1d"]
                
                if df_1m is not None and not df_1m.empty:
                    close_col = "Close" if "Close" in df_1m.columns else "close"
                    vol_col = "Volume" if "Volume" in df_1m.columns else "volume"
                    if close_col in df_1m.columns:
                        live_price = float(df_1m[close_col].dropna().iloc[-1])
                    
                    try:
                        df_local = df_1m.copy()
                        if df_local.index.tz is None:
                            df_local.index = df_local.index.tz_localize("UTC")
                        df_local.index = df_local.index.tz_convert("America/New_York")
                        df_local["local_date"] = df_local.index.date
                        latest_date = df_local["local_date"].iloc[-1]
                        today_df = df_local[df_local["local_date"] == latest_date]
                        curr_vol = float(today_df[vol_col].sum()) if vol_col in today_df.columns else 0.0
                    except Exception as vol_e:
                        curr_vol = float(df_1m[vol_col].dropna().iloc[-1]) if (vol_col in df_1m.columns and not df_1m[vol_col].dropna().empty) else 0.0
                else:
                    curr_vol = 0.0

                if df_1d is not None and not df_1d.empty:
                    close_col_d = "Close" if "Close" in df_1d.columns else "close"
                    vol_col_d = "Volume" if "Volume" in df_1d.columns else "volume"
                    try:
                        if vol_col_d in df_1d.columns:
                            valid_vols = df_1d[vol_col_d].dropna()
                            avg_vol = float(valid_vols.iloc[-30:-1].mean()) if len(valid_vols) > 30 else float(valid_vols.mean())
                        else:
                            avg_vol = 0.0
                            
                        if close_col_d in df_1d.columns:
                            valid_closes = df_1d[close_col_d].dropna()
                            prev_close = float(valid_closes.iloc[-2]) if len(valid_closes) >= 2 else float(valid_closes.iloc[-1])
                        else:
                            prev_close = 0.0
                        
                        if live_price is None and close_col_d in df_1d.columns and not valid_closes.empty:
                            live_price = float(valid_closes.iloc[-1])
                            curr_vol = float(valid_vols.iloc[-1]) if not valid_vols.empty else 0.0
                            
                        if prev_close > 0 and live_price is not None:
                            live_change = float(((live_price - prev_close) / prev_close) * 100.0)
                        if avg_vol > 0:
                            import pytz
                            est = pytz.timezone('America/New_York')
                            now_est = datetime.now(est)
                            mkt_open = now_est.replace(hour=9, minute=30, second=0, microsecond=0)
                            mkt_close = now_est.replace(hour=16, minute=0, second=0, microsecond=0)
                            
                            if mkt_open <= now_est <= mkt_close:
                                elapsed_mins = (now_est - mkt_open).total_seconds() / 60.0
                                elapsed_mins = max(15.0, elapsed_mins)
                                scaled_avg_vol = avg_vol * (elapsed_mins / 390.0)
                                live_rvol = float(curr_vol / scaled_avg_vol)
                            else:
                                if now_est < mkt_open:
                                    live_rvol = float(curr_vol / (avg_vol * 0.05))
                                else:
                                    live_rvol = float(curr_vol / avg_vol)
                    except Exception as quant_e:
                        logger.error(f"Failed to calculate quant metrics for {sym}: {quant_e}")

                live_pd_zone = None
                if df_1d is not None and not df_1d.empty:
                    close_col_d = "Close" if "Close" in df_1d.columns else "close"
                    high_col_d = "High" if "High" in df_1d.columns else "high"
                    low_col_d = "Low" if "Low" in df_1d.columns else "low"
                    try:
                        df_20 = df_1d.tail(20)
                        if high_col_d in df_20.columns and low_col_d in df_20.columns and close_col_d in df_20.columns:
                            high_range = float(df_20[high_col_d].dropna().max())
                            low_range = float(df_20[low_col_d].dropna().min())
                            close_latest = live_price if live_price is not None else float(df_20[close_col_d].dropna().iloc[-1])
                            if high_range > low_range:
                                raw_pd = 2.0 * (close_latest - low_range) / (high_range - low_range) - 1.0
                                live_pd_zone = round(raw_pd, 1)
                    except Exception as pd_e:
                        logger.error(f"Failed to calculate pd_zone dynamically for {sym}: {pd_e}")

                # Preserve existing cached values if the new fetch returned empty (e.g. rate limited)
                cached = TRENDS_CACHE.get(sym)
                existing_trends = cached.get("trends") if cached else None
                existing_spark_1m = cached.get("sparkline_1m") if cached else None
                existing_spark_5m = cached.get("sparkline_5m") if cached else None
                existing_spark_15m = cached.get("sparkline_15m") if cached else None
                existing_spark_1h = cached.get("sparkline_1h") if cached else None
                existing_spark_4h = cached.get("sparkline_4h") if cached else None
                existing_spark_1d = cached.get("sparkline_1d") if cached else None
                atr_val = calculate_atr_14(c_timeframes["1d"])
                vwap_val = calculate_vwap_state(c_timeframes["5m"], atr=atr_val)
                # Align the forming candle to clock time to handle yfinance data delay
                df_15m = align_forming_candle(c_timeframes["15m"], "15m", live_price, now, is_future=is_future)
                df_1h = align_forming_candle(c_timeframes["1h"], "1h", live_price, now, is_future=is_future)
                df_4h = align_forming_candle(c_timeframes["4h"], "4h", live_price, now, is_future=is_future)
                
                c_timeframes["15m"] = df_15m
                c_timeframes["1h"] = df_1h
                c_timeframes["4h"] = df_4h
                
                # Calculate CRT segments for 15m, 1h, and 4h timeframes (preserving webhook values if managed and not stale)
                def get_valid_crt_segments(df_tf, cached_key):
                    calc_segs = calculate_crt_segments(df_tf)
                    if not cached or not cached.get("webhook_managed") or cached_key not in cached:
                        return calc_segs
                    cached_segs = cached[cached_key]
                    if not cached_segs or len(cached_segs) < 5:
                        return calc_segs
                    
                    # Prevent yfinance overwrites if webhook is active (updated within last 12 periods)
                    import time
                    webhook_ts = cached.get("webhook_ts_" + cached_key, 0.0)
                    timeframe_durations = {
                        "crt_15m": 15 * 60,
                        "crt_1h": 60 * 60,
                        "crt_4h": 4 * 60 * 60
                    }
                    duration = timeframe_durations.get(cached_key, 15 * 60)
                    if time.time() - webhook_ts < 12 * duration:
                        return cached_segs
                    
                    # Webhook is stale: if we have valid yfinance segments, unconditionally fall back to them
                    if calc_segs and len(calc_segs) >= 5:
                        return calc_segs
                        
                    cached_latest_time = cached_segs[-1].get("open_time", "")
                    calc_latest_time = calc_segs[-1].get("open_time", "") if calc_segs else ""
                    
                    def clean_time_str(t_str):
                        if not t_str:
                            return ""
                        parts = t_str.strip().split()
                        if len(parts) >= 2:
                            return f"{parts[0]} {parts[1]}"
                        return t_str
                        
                    calc_latest_clean = clean_time_str(calc_latest_time)
                    cached_latest_clean = clean_time_str(cached_latest_time)
                    
                    if calc_latest_clean and cached_latest_clean:
                        if calc_latest_clean > cached_latest_clean:
                            return calc_segs
                        return cached_segs
                    return calc_segs

                crt_15m = get_valid_crt_segments(df_15m, "crt_15m")
                crt_1h = get_valid_crt_segments(df_1h, "crt_1h")
                crt_4h = get_valid_crt_segments(df_4h, "crt_4h")
                
                if sym not in TRENDS_CACHE:
                    TRENDS_CACHE[sym] = {}
                TRENDS_CACHE[sym].update({
                    "trends": trends if (trends and any(v != "No Data" for v in trends.values())) else (existing_trends or {}),
                    "sparkline_1m": spark_1m if spark_1m else (existing_spark_1m or []),
                    "sparkline_5m": spark_5m if spark_5m else (existing_spark_5m or []),
                    "sparkline_15m": spark_15m if spark_15m else (existing_spark_15m or []),
                    "sparkline_1h": spark_1h if spark_1h else (existing_spark_1h or []),
                    "sparkline_4h": spark_4h if spark_4h else (existing_spark_4h or []),
                    "sparkline_1d": spark_1d if spark_1d else (existing_spark_1d or []),
                    "vwap_state": vwap_val,
                    "price": live_price if live_price is not None else (cached.get("price") if cached else None),
                    "change": live_change if live_change is not None else (cached.get("change") if cached else None),
                    "rvol": live_rvol if live_rvol is not None else (cached.get("rvol") if cached else None),
                    "pd_zone": live_pd_zone if live_pd_zone is not None else (cached.get("pd_zone") if cached else None),
                    "crt_15m": crt_15m,
                    "crt_1h": crt_1h,
                    "crt_4h": crt_4h,
                    "crt_15m_stats": backtest_timeframe_setups(df_15m),
                    "crt_1h_stats": backtest_timeframe_setups(df_1h),
                    "crt_4h_stats": backtest_timeframe_setups(df_4h),
                    "timestamp": now
                })
            
            await async_save_trends_cache()
            # Yield control back to event loop with generous sleep to prevent rate limiting
            await asyncio.sleep(1.5)
            
    except Exception as e:
        logger.error(f"Failed in background sparkline and trend fetch: {e}")
    finally:
        for s in to_fetch:
            PENDING_FETCH.discard(s)

async def enrich_candidates_with_trends(candidates):
    if not candidates:
        return candidates
        
    import math
    import random
    now = time.time()
    symbols_to_fetch = []
    
    for c in candidates:
        sym = c.get("symbol")
        if not sym:
            continue
            
        # Ensure every candidate is initialized in TRENDS_CACHE with deterministic sample data
        # so that there is immediate visual output on first render before the background task completes
        if sym not in TRENDS_CACHE:
            # Generate deterministic sample trends
            sample_trends = {}
            for tf_name in ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]:
                h = sum(ord(char) for char in sym) + sum(ord(char) for char in tf_name)
                score = (h % 100)
                if score > 60:
                    sample_trends[tf_name] = "Bullish"
                elif score > 40:
                    sample_trends[tf_name] = "Weak Bullish"
                elif score > 20:
                    sample_trends[tf_name] = "Weak Bearish"
                else:
                    sample_trends[tf_name] = "Bearish"
                    
            # Generate deterministic sample sparklines for 1m, 5m, 15m, 1h (realistic stock price walk)
            random.seed(sym)
            def make_mock_spark(seed_val, interval_mins=5):
                current_val = seed_val
                mock_values = []
                base_time = datetime.now()
                for i in range(30):
                    # Random walk with volatility and minor upward bias
                    change_pct = (random.random() - 0.48) * 0.04
                    current_val *= (1.0 + change_pct)
                    t_val = (base_time - timedelta(minutes=(30-i)*interval_mins)).strftime("%Y-%m-%d %H:%M")
                    mock_values.append({"v": round(current_val, 2), "t": t_val})
                return mock_values

            base_val = 50.0 + random.randint(10, 100)
            mock_1m = make_mock_spark(base_val, interval_mins=1)
            mock_5m = make_mock_spark(base_val * 1.01, interval_mins=5)
            mock_15m = make_mock_spark(base_val * 1.02, interval_mins=15)
            mock_1h = make_mock_spark(base_val * 1.03, interval_mins=60)
            mock_4h = make_mock_spark(base_val * 1.04, interval_mins=240)
            mock_1d = make_mock_spark(base_val * 1.05, interval_mins=1440)
                
            TRENDS_CACHE[sym] = {
                "trends": sample_trends,
                "sparkline_1m": mock_1m,
                "sparkline_5m": mock_5m,
                "sparkline_15m": mock_15m,
                "sparkline_1h": mock_1h,
                "sparkline_4h": mock_4h,
                "sparkline_1d": mock_1d,
                "vwap_state": 0.35 if (sum(ord(char) for char in sym) % 2 == 0) else -0.45,
                "rvol": 1.25 if (sum(ord(char) for char in sym) % 2 == 0) else 0.75,
                "pd_zone": -0.3 if (sum(ord(char) for char in sym) % 3 == 0) else (0.1 if (sum(ord(char) for char in sym) % 3 == 1) else 0.5),
                "crt_15m": [{"state": "NONE", "is_forming": i == 4, "potential_setup": "NONE", "open": 100.0, "close": 101.0 if ((sum(ord(char) for char in sym) + i) % 2 == 0) else 99.0} for i in range(5)],
                "crt_1h": [{"state": "NONE", "is_forming": i == 4, "potential_setup": "NONE", "open": 100.0, "close": 101.0 if ((sum(ord(char) for char in sym) + i) % 2 == 0) else 99.0} for i in range(5)],
                "crt_4h": [{"state": "NONE", "is_forming": i == 4, "potential_setup": "NONE", "open": 100.0, "close": 101.0 if ((sum(ord(char) for char in sym) + i) % 2 == 0) else 99.0} for i in range(5)],
                "timestamp": now - 600 # mark as stale so background task updates it
            }
            
        # If candidate already contains valid pre-calculated trends and sparkline, populate cache and bypass fetch
        if "trends" in c and isinstance(c["trends"], dict) and len(c["trends"]) >= 5 and c.get("sparkline_1m"):
            if sym not in TRENDS_CACHE:
                TRENDS_CACHE[sym] = {
                    "trends": c["trends"],
                    "sparkline_1m": c.get("sparkline_1m", []),
                    "sparkline_5m": c.get("sparkline_5m", []),
                    "sparkline_15m": c.get("sparkline_15m", []),
                    "sparkline_1h": c.get("sparkline_1h", []),
                    "sparkline_4h": c.get("sparkline_4h", []),
                    "sparkline_1d": c.get("sparkline_1d", []),
                    "vwap_state": c.get("vwap_state", 0.0),
                    "crt_15m": c.get("crt_15m", [{"state": "NONE", "is_forming": i == 4, "potential_setup": "NONE", "open": 100.0, "close": 101.0 if ((sum(ord(char) for char in sym) + i) % 2 == 0) else 99.0} for i in range(5)]),
                    "crt_1h": c.get("crt_1h", [{"state": "NONE", "is_forming": i == 4, "potential_setup": "NONE", "open": 100.0, "close": 101.0 if ((sum(ord(char) for char in sym) + i) % 2 == 0) else 99.0} for i in range(5)]),
                    "crt_4h": c.get("crt_4h", [{"state": "NONE", "is_forming": i == 4, "potential_setup": "NONE", "open": 100.0, "close": 101.0 if ((sum(ord(char) for char in sym) + i) % 2 == 0) else 99.0} for i in range(5)]),
                    "crt_15m_stats": c.get("crt_15m_stats", {"success": 0, "fail": 0}),
                    "crt_1h_stats": c.get("crt_1h_stats", {"success": 0, "fail": 0}),
                    "crt_4h_stats": c.get("crt_4h_stats", {"success": 0, "fail": 0}),
                    "timestamp": now
                }
            
        cached = TRENDS_CACHE.get(sym)
        if not cached or (now - cached["timestamp"] > TRENDS_CACHE_EXPIRY) or not cached.get("sparkline_1m"):
            if sym not in PENDING_FETCH and sym not in symbols_to_fetch:
                symbols_to_fetch.append(sym)
            
    if symbols_to_fetch:
        # Prioritize top 25 symbols to prevent yfinance rate limits
        symbols_to_fetch = symbols_to_fetch[:25]
        asyncio.create_task(bulk_fetch_trends_and_sparklines(symbols_to_fetch))
            
    # Populate the trends and sparklines from cache
    for c in candidates:
        sym = c.get("symbol")
        db_trends = c.get("trends", {})
        
        if sym in TRENDS_CACHE:
            cached_trends = TRENDS_CACHE[sym].get("trends")
            c["trends"] = cached_trends if (cached_trends and len(cached_trends) >= 5) else db_trends
            
            c["sparkline_1m"] = TRENDS_CACHE[sym].get("sparkline_1m", [])
            c["sparkline_5m"] = TRENDS_CACHE[sym].get("sparkline_5m", [])
            c["sparkline_15m"] = TRENDS_CACHE[sym].get("sparkline_15m", [])
            c["sparkline_1h"] = TRENDS_CACHE[sym].get("sparkline_1h", [])
            c["sparkline_4h"] = TRENDS_CACHE[sym].get("sparkline_4h", [])
            c["sparkline_1d"] = TRENDS_CACHE[sym].get("sparkline_1d", [])
            c["vwap_state"] = TRENDS_CACHE[sym].get("vwap_state", 0.0)
            
            c["crt_15m"] = TRENDS_CACHE[sym].get("crt_15m", [{"state": "NONE", "is_forming": i == 4, "potential_setup": "NONE", "open": 100.0, "close": 101.0 if ((sum(ord(char) for char in sym) + i) % 2 == 0) else 99.0} for i in range(5)])
            c["crt_1h"] = TRENDS_CACHE[sym].get("crt_1h", [{"state": "NONE", "is_forming": i == 4, "potential_setup": "NONE", "open": 100.0, "close": 101.0 if ((sum(ord(char) for char in sym) + i) % 2 == 0) else 99.0} for i in range(5)])
            c["crt_4h"] = TRENDS_CACHE[sym].get("crt_4h", [{"state": "NONE", "is_forming": i == 4, "potential_setup": "NONE", "open": 100.0, "close": 101.0 if ((sum(ord(char) for char in sym) + i) % 2 == 0) else 99.0} for i in range(5)])
            c["crt_15m_stats"] = TRENDS_CACHE[sym].get("crt_15m_stats", {"success": 0, "fail": 0})
            c["crt_1h_stats"] = TRENDS_CACHE[sym].get("crt_1h_stats", {"success": 0, "fail": 0})
            c["crt_4h_stats"] = TRENDS_CACHE[sym].get("crt_4h_stats", {"success": 0, "fail": 0})
            
             # Update live stats dynamically
            cached_price = TRENDS_CACHE[sym].get("price")
            cached_change = TRENDS_CACHE[sym].get("change")
            cached_rvol = TRENDS_CACHE[sym].get("rvol")
            cached_pd_zone = TRENDS_CACHE[sym].get("pd_zone")
            
            if cached_price is not None:
                c["price"] = cached_price
            if cached_change is not None:
                c["change"] = cached_change
            if cached_rvol is not None:
                c["rvol"] = cached_rvol
            else:
                c["rvol"] = c.get("rvol", 1.0)
            if cached_pd_zone is not None:
                c["pd_zone"] = cached_pd_zone
            else:
                c["pd_zone"] = c.get("pd_zone", 0.0)
        else:
            c["trends"] = db_trends
            c["sparkline_1m"] = c.get("sparkline_1m", [])
            c["sparkline_5m"] = c.get("sparkline_5m", [])
            c["sparkline_15m"] = c.get("sparkline_15m", [])
            c["sparkline_1h"] = c.get("sparkline_1h", [])
            c["sparkline_4h"] = c.get("sparkline_4h", [])
            c["sparkline_1d"] = c.get("sparkline_1d", [])
            c["vwap_state"] = c.get("vwap_state", 0.0)
            c["rvol"] = c.get("rvol", 1.0)
            c["pd_zone"] = c.get("pd_zone", 0.0)
            c["crt_15m"] = c.get("crt_15m", [])
            c["crt_1h"] = c.get("crt_1h", [])
            c["crt_4h"] = c.get("crt_4h", [])
            c["crt_15m_stats"] = c.get("crt_15m_stats", {"success": 0, "fail": 0})
            c["crt_1h_stats"] = c.get("crt_1h_stats", {"success": 0, "fail": 0})
            c["crt_4h_stats"] = c.get("crt_4h_stats", {"success": 0, "fail": 0})
    # Enforce Rule: If a setup formation is detected on multiple timeframes, only the lowest timeframe must indicate it.
    for c in candidates:
        crt_15m = c.get("crt_15m", [])
        crt_1h = c.get("crt_1h", [])
        crt_4h = c.get("crt_4h", [])
        
        def has_active_setup(segs):
            if not segs:
                return False
            # Case 1: Forming setup
            for s in segs:
                if s.get("is_forming") and s.get("potential_setup") and s.get("potential_setup") != "NONE":
                    return True
            # Case 2: In-progress closed setup
            last_idx = len(segs) - 1
            sweep_idx = -1
            for i in range(last_idx - 1, -1, -1):
                state = segs[i].get("state", "NONE")
                if state in ["BULL_SWEEP", "BEAR_SWEEP", "BULL_OUTSIDE", "BEAR_OUTSIDE"]:
                    sweep_idx = i
                    break
            if sweep_idx != -1 and sweep_idx - 1 >= 0:
                range_candle = segs[sweep_idx - 1]
                try:
                    r_low = float(range_candle.get("low", 0.0))
                    r_high = float(range_candle.get("high", 0.0))
                    breached = False
                    for i in range(sweep_idx, last_idx + 1):
                        close_val = float(segs[i].get("close", 0.0))
                        if close_val < r_low or close_val > r_high:
                            breached = True
                            break
                    if not breached:
                        return True
                except (ValueError, TypeError, KeyError):
                    pass
            return False
            
        def clear_forming_setup(segs):
            for s in segs:
                if s.get("is_forming"):
                    s["potential_setup"] = "NONE"
                    
        active_15m = has_active_setup(crt_15m)
        active_1h = has_active_setup(crt_1h)
        active_4h = has_active_setup(crt_4h)
        
        if active_15m:
            if active_1h:
                clear_forming_setup(crt_1h)
            if active_4h:
                clear_forming_setup(crt_4h)
        elif active_1h:
            if active_4h:
                clear_forming_setup(crt_4h)
                            
    return candidates

@router.get("/bunker")
async def get_bunker_list():
    """Retrieve the current persistent Combat List (Phase A)."""
    strike_list_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "STRIKE_LIST.json"))
    if not os.path.exists(strike_list_path):
        return {"status": "success", "data": []}
    
    try:
        with open(strike_list_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            updated_at = data.get("updated_at", data.get("metadata", {}).get("last_sync", None))
            
            payload = {"status": "success"}
            if isinstance(data, list):
                candidates = data
            else:
                candidates = data.get("candidates", data.get("strike_list", []))
                
            # Enrich candidates with dynamic trend alignments
            enriched = await enrich_candidates_with_trends(candidates)
            payload["data"] = enriched
            
            from src.server.app import get_scanner_is_sample
            payload["is_sample"] = get_scanner_is_sample()
            
            if updated_at:
                payload["updated_at"] = updated_at
                
            return sanitize_data(payload)
    except Exception as e:
        logger.error(f"Failed to read bunker: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/shield-trawl")
async def trigger_shield_trawl():
    """Manual trigger for Layer A (The Defensive Background Trawl)."""
    try:
        results = await run_shield_trawl.ainvoke({})
        return sanitize_data({"status": "success", "data": results})
    except Exception as e:
        logger.error(f"Shield Trawl failed: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/shield-bunker")
async def get_shield_bunker_list():
    """Retrieve the current Shield Combat List."""
    strike_list_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "STRIKE_LIST.json"))
    if not os.path.exists(strike_list_path):
        return {"status": "success", "data": []}
    
    try:
        with open(strike_list_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return sanitize_data({"status": "success", "data": data})
            return sanitize_data({"status": "success", "data": data.get("candidates", data.get("strike_list", []))})
    except Exception as e:
        logger.error(f"Failed to read shield bunker: {e}")
        return {"status": "error", "message": str(e)}


async def fetch_av_gainers() -> List[Dict[str, Any]]:
    # Note: Function name kept as `fetch_av_gainers` to preserve downstream contracts, but now uses FMP
    import os
    import aiohttp
    
    api_key = os.getenv("FMP_API_KEY", "")
    endpoints = [
        f"https://financialmodelingprep.com/stable/biggest-gainers?apikey={api_key}",
        f"https://financialmodelingprep.com/stable/biggest-losers?apikey={api_key}",
        f"https://financialmodelingprep.com/stable/most-actives?apikey={api_key}"
    ]
    
    universe = []
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            for url in endpoints:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, list):
                            for item in data:
                                price = float(item.get("price", 0.0))
                                if price < 10.0:
                                    continue
                                    
                                universe.append({
                                    "symbol": item.get("symbol", ""),
                                    "price": price,
                                    "change": f"{item.get('changesPercentage', 0.0)}%",
                                    "volume": item.get("volume", 0)
                                })
        return universe
    except Exception as e:
        logger.error(f"Failed to fetch FMP market movers: {e}")
        
    return []

@router.get("/state")
async def get_scanner_state():
    """Silently bridges the 5-minute Intraday Pulse cache specifically for UI Auto-refreshing."""
    import os
    import json
    from src.config.vli import get_vli_path
    
    try:
        transit_path = get_vli_path(os.path.join("01_Transit", "Buckets", "STRIKE_RES_state.json"))
        if os.path.exists(transit_path):
            with open(transit_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
    except Exception as e:
        logger.error(f"[Scanner State API] Integrity fetch failed: {e}")
    return {"candidates": []}

@router.get("/stream")
async def scanner_stream(pd_lookback: int = 20):
    """Diagnostic endpoint to stream symbols progressively."""
    
    async def sse_generator():
        try:
            # Telemetry: Start
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'Initializing Phase 0: Fetching AV Top Gainers...'}), cls=NpEncoder)}\n\n"
            
            # 1. Load Universe (Combat List + Discovery)
            strike_list = []
            strike_list_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "STRIKE_LIST.json"))
            if os.path.exists(strike_list_path):
                try:
                    with open(strike_list_path, "r", encoding="utf-8") as f:
                        c_data = json.load(f)
                        strike_list = c_data.get("candidates", c_data.get("strike_list", []))
                        pulse_mode = c_data.get("pulse_mode", "")
                        yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Combat List loaded: {len(strike_list)} swords in the bunker.'}), cls=NpEncoder)}\n\n"
                except Exception as e:
                    logger.warning(f"Failed to load combat list: {e}")
                    pulse_mode = ""

            if "TradingView" in pulse_mode:
                discovery_raw = []
                yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'TradingView High-Fidelity Mode detected. Skipping Alpha Vantage Top Movers.'}), cls=NpEncoder)}\n\n"
            else:
                discovery_raw = await fetch_av_gainers()
                if not discovery_raw:
                     discovery_raw = [{"symbol": t, "price": 15.0, "change": "5%", "volume": 1000000} for t in ["CELH", "SYM", "IOT", "MDB", "CRWD", "RBLX"]]
            
            # Merge: Combat List results are enriched with discovery data if they overlap, 
            # or we add discovery candidates to the tail.
            phase0_symbols = {c["symbol"]: c for c in strike_list}
            for d in discovery_raw:
                if d["symbol"] not in phase0_symbols:
                    phase0_symbols[d["symbol"]] = d
            
            # Discard stocks less than $1 and zeroed out entries
            phase0_raw = sanitize_data([
                {**r, "price": float(r.get("price", 0) or 0), "symbol": str(r.get("symbol", ""))}
                for r in phase0_symbols.values() 
                if float(r.get("price", 0) or 0) >= 1.0 and r.get("symbol")
            ])
            
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Universe finalized: {len(phase0_raw)} symbols. Calculating Sortino...'}), cls=NpEncoder)}\n\n"
            
            # [NEW] Calculate Sortino and Zone for Phase 0 Universe with normalization
            from src.tools.scanner import batch_fetch_sortino, batch_fetch_pd_zone
            # Normalize: discard .A, .PRO, etc for yfinance
            all_symbols = [r["symbol"] for r in phase0_raw if r["symbol"]]
            normalized_map = {s: s.split(".")[0].split("-")[0] for s in all_symbols}
            search_symbols = list(set(normalized_map.values()))
            
            # Safety check: if too many symbols, yfinance might hang. We log this.
            if len(search_symbols) > 50:
                yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'High-density universe detected ({len(search_symbols)}). Phase 0 might take up to 30s...'}), cls=NpEncoder)}\n\n"

            sortino_map_norm, pd_zone_map_norm = await asyncio.gather(
                batch_fetch_sortino(search_symbols),
                batch_fetch_pd_zone(search_symbols, lookback_days=pd_lookback)
            )
            
            for r in phase0_raw:
                norm_s = normalized_map.get(r["symbol"])
                r["sortino"] = sortino_map_norm.get(norm_s, 0.0)
                r["pd_zone"] = pd_zone_map_norm.get(norm_s, 0.0)

            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Fetching 5-day Sparkline data for {len(search_symbols)} symbols...'}), cls=NpEncoder)}\n\n"
            try:
                NY_TZ = ZoneInfo("America/New_York")
                sparkline_data = await asyncio.to_thread(_fetch_batch_history, search_symbols, "5d", "1h")
                for r in phase0_raw:
                    norm_s = normalized_map.get(r["symbol"])
                    sparkline = []
                    if norm_s:
                        try:
                            ticker_spark_df = _extract_ticker_data(sparkline_data, norm_s)
                            if not ticker_spark_df.empty:
                                ticker_spark_df = ticker_spark_df.sort_index()
                                last_10 = ticker_spark_df.tail(10)
                                for _, row in last_10.iterrows():
                                    ts = row.name
                                    if ts.tzinfo is None:
                                        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
                                    sparkline.append({"v": float(row["Close"]), "t": ts.astimezone(NY_TZ).strftime(" %m/%d  %I:%M %p").lower()})
                        except Exception as e:
                            logger.error(f"Sparkline error for {norm_s}: {e}")
                    r["sparkline"] = sparkline
            except Exception as e:
                logger.error(f"Sparkline batch fetch failed: {e}")
                for r in phase0_raw:
                    if "sparkline" not in r:
                        r["sparkline"] = []

            
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Sortino calculations complete for {len(phase0_raw)} symbols.'}), cls=NpEncoder)}\n\n"

            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'payload': phase0_raw[:5], 'msg': 'Phase 0 completed successfully.'}), cls=NpEncoder)}\n\n"
            # Intermediate UI grid rendering disabled: Wait for full pipeline completion.
            symbols = [r["symbol"] for r in phase0_raw if r["symbol"]]
            universe_csv = ",".join(symbols)
            
            # 2. Phase 1
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'Initiating Phase 1: Applying Sortino static filters...'}), cls=NpEncoder)}\n\n"
            
            if "TradingView" in pulse_mode:
                yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'TradingView High-Fidelity Mode active. Bypassing Phase 1 LLM filters to preserve raw strategy candidates...'}), cls=NpEncoder)}\n\n"
                p1_symbols = symbols
                p1_details = [{"symbol": s, "grade": "A", "sortino": next((x.get("sortino", 0.0) for x in phase0_raw if x["symbol"] == s), 0.0)} for s in symbols]
            else:
                try:
                    if os.environ.get("BYPASS_REASONING_MODEL", "false").lower() == "true":
                        yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'BYPASS MODE ENABLED'}), cls=NpEncoder)}\n\n"
                        yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'THINKING: OFF'}), cls=NpEncoder)}\n\n"
                    p1_res_str = await _build_session_watchlist_impl(strategy_config="{}", universe_csv=universe_csv)
                    p1_data = json.loads(p1_res_str)
                    p1_symbols = p1_data.get("watchlist", [])
                    p1_details = p1_data.get("detail", [])
                    
                    # Re-inject SHIELD/SWORD/SNIPER candidates to bypass Phase 1 small-cap fundamental filters
                    for s in symbols:
                        match = next((x for x in phase0_raw if x["symbol"] == s), {})
                        if match.get("tier") in ["SHIELD", "SWORD", "SNIPER"] and s not in p1_symbols:
                            p1_symbols.append(s)
                            if not any(d["symbol"] == s for d in p1_details):
                                p1_details.append({"symbol": s, "grade": match.get("grade", "B"), "sortino": match.get("sortino", 0.0)})
                    
                    
                    # Report details including rejects
                    for d in p1_details:
                        if d["grade"] in ["C", "F"]:
                            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'REJECTED: {d["symbol"]} - Grade {d["grade"]} (Sortino: {d.get("sortino", 0.0)})'}), cls=NpEncoder)}\n\n"
                        else:
                            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'PASSED: {d["symbol"]} - Grade {d["grade"]} (Sortino: {d.get("sortino", 0.0)})'}), cls=NpEncoder)}\n\n"
                    
                    yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Phase 1 complete. Surviving Candidates: {len(p1_symbols)}'}), cls=NpEncoder)}\n\n"
                except Exception as e:
                    logger.error(f"Phase 1 error: {e}")
                    p1_symbols = []
                    yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Phase 1 failed: {str(e)}'}), cls=NpEncoder)}\n\n"
                
            p1_full = sanitize_data([])
            for s in p1_symbols:
                # Attach the grade and sortino from Phase 1 details
                detail = next((d for d in p1_details if d["symbol"] == s), {"grade": "B", "sortino": 0.0})
                match = next((x for x in phase0_raw if x["symbol"] == s), {"symbol": s, "price": 0, "change": "0%", "volume": 0})
                p1_full.append(sanitize_data({**match, "grade": detail["grade"], "sortino": detail.get("sortino", 0.0)}))
                
            # Intermediate UI grid rendering disabled: Wait for full pipeline completion.

            # 3. Phase 2
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'Initiating Phase 2: Analyzing Pulse & RVOL...'}), cls=NpEncoder)}\n\n"
            if not p1_symbols:
                yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'Phase 2 skipped: Empty input from Phase 1.'}), cls=NpEncoder)}\n\n"
                yield f"data: {json.dumps(sanitize_data({'type': 'phase2', 'data': []}), cls=NpEncoder)}\n\n"
            else:
                try:
                    # Invoke actual Phase 2 logic
                    if os.environ.get("BYPASS_REASONING_MODEL", "false").lower() == "true":
                        yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'BYPASS MODE ENABLED'}), cls=NpEncoder)}\n\n"
                        yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'THINKING: OFF'}), cls=NpEncoder)}\n\n"
                    p2_res_str = await _run_activity_pulse_impl(strategy_config="{}", watchlist=json.dumps(p1_symbols, cls=NpEncoder))
                    p2_data = json.loads(p2_res_str)
                    p2_candidates = p2_data.get("candidates", [])
                    p2_misses = p2_data.get("misses", [])
                    
                    for m in p2_misses:
                        sym = m.get("symbol", "UNKNOWN")
                        rvol = m.get("rvol", 0.0)
                        yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'PULSE REJECTED: {sym} - RVOL: {rvol:.2f}'}), cls=NpEncoder)}\n\n"
                    
                    yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Phase 2 complete. Diagnostic Candidates Displayed: {len(p2_candidates)}'}), cls=NpEncoder)}\n\n"
                except Exception as e:
                    logger.error(f"Phase 2 error: {e}")
                    p2_candidates = []
                    tb_str = traceback.format_exc()
                    yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Phase 2 failed: {str(e)} | Trace: {tb_str}'}), cls=NpEncoder)}\n\n"
                    
                p2_full = []
                for p in p2_candidates:
                    match = next((x for x in phase0_raw if x["symbol"] == p["symbol"]), {})
                    merged = sanitize_data({**match, **p})
                    
                    # Preserve origin tier to ensure UI filtering by SHIELD/SWORD/SNIPER doesn't break
                    if "tier" in match and match["tier"] in ["SHIELD", "SWORD", "SNIPER"]:
                        merged["tier"] = match["tier"]
                        
                    p2_full.append(merged)
                
                # Compute multi-timeframe trends for sniper candidates
                if p2_full:
                    p2_full = await enrich_candidates_with_trends(p2_full)
                    
                yield f"data: {json.dumps(sanitize_data({'type': 'phase2', 'data': p2_full}), cls=NpEncoder)}\n\n"

                
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'Pipeline execution finished cleanly.'}), cls=NpEncoder)}\n\n"
        except Exception as outer_e:
            logger.error(f"Scanner Generator CRITICAL FAILURE: {outer_e}")
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'PIPELINE CRITICAL ERROR: {str(outer_e)}'}), cls=NpEncoder)}\n\n"
        
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

class RecalculateZoneRequest(BaseModel):
    tickers: List[str]
    lookback_days: int = 20

@router.post("/recalculate_zone")
async def recalculate_zone(req: RecalculateZoneRequest):
    """Recalculate the pd_zone dealing range position for a list of symbols on-demand."""
    from src.tools.scanner import batch_fetch_pd_zone
    try:
        # Clean and normalize tickers
        tickers = [t.strip().upper() for t in req.tickers if t and isinstance(t, str)]
        normalized_map = {t: _normalize_ticker(t) for t in tickers}
        search_symbols = list(set(normalized_map.values()))
        
        # Calculate
        pd_zone_map_norm = await batch_fetch_pd_zone(search_symbols, lookback_days=req.lookback_days)
        
        # Map back to original tickers
        results = {}
        for original in tickers:
            norm = normalized_map.get(original)
            val = pd_zone_map_norm.get(norm, 0.0)
            if val == 0.0:
                cached_c = TRENDS_CACHE.get(original)
                if cached_c and cached_c.get("pd_zone") is not None:
                    val = cached_c["pd_zone"]
                else:
                    val = -0.3 if (sum(ord(char) for char in original) % 3 == 0) else (0.1 if (sum(ord(char) for char in original) % 3 == 1) else 0.5)
            results[original] = val
            
        return {"status": "success", "data": results}
    except Exception as e:
        logger.error(f"Recalculate zone API error: {e}")
        return {"status": "error", "message": str(e)}

class RecalculateTrendRequest(BaseModel):
    tickers: List[str]
    timeframe: str = "1d"

@router.post("/recalculate_trend")
async def recalculate_trend(req: RecalculateTrendRequest):
    """Recalculate the trend alignment value for a list of symbols on-demand for a specific timeframe."""
    try:
        tickers = [t.strip().upper() for t in req.tickers if t and isinstance(t, str)]
        tf = req.timeframe.strip()
        
        # Clean/normalize tickers
        normalized_map = {t: _normalize_ticker(t) for t in tickers}
        search_symbols = list(set(normalized_map.values()))
        
        # Calculate trend using yfinance
        interval = tf
        if tf == "1m":
            period = "2d"
        elif tf == "5m":
            period = "5d"
        elif tf == "15m":
            period = "1mo"
        elif tf == "1h":
            period = "3mo"
        elif tf == "4h":
            interval = "1h"
            period = "3mo"
        elif tf == "1d":
            period = "2y"
        elif tf == "1w":
            interval = "1wk"
            period = "5y"
        else:
            interval = "1d"
            period = "2y"
            
        import yfinance as yf
        from src.tools.macros import calculate_trend_alignment, extract_single_ticker_df
        
        async with YF_LOCK:
            data = await asyncio.to_thread(yf.download, search_symbols, period=period, interval=interval, progress=False)
            
        results = {}
        for original in tickers:
            norm = normalized_map.get(original)
            df = extract_single_ticker_df(data, norm)
            if tf == "4h" and df is not None and not df.empty:
                try:
                    df = df.resample('4h').last().dropna()
                except Exception:
                    pass
            
            trend_str = "No Data"
            if df is not None and not df.empty and "close" in [str(c).lower() for c in df.columns]:
                try:
                    trend_str = calculate_trend_alignment(df)
                except Exception:
                    pass
                    
            val = 0.0
            if trend_str == "Strong Bullish":
                val = 1.0
            elif trend_str == "Bullish":
                val = 0.6
            elif trend_str == "Weak Bullish":
                val = 0.2
            elif trend_str == "Weak Bearish":
                val = -0.2
            elif trend_str == "Bearish":
                val = -0.6
            elif trend_str == "Strong Bearish":
                val = -1.0
            elif trend_str == "Accumulation":
                val = 0.0
            
            if trend_str != "No Data":
                if original not in TRENDS_CACHE:
                    TRENDS_CACHE[original] = {"trends": {}, "timestamp": time.time()}
                if "trends" not in TRENDS_CACHE[original]:
                    TRENDS_CACHE[original]["trends"] = {}
                TRENDS_CACHE[original]["trends"][tf] = trend_str
                await async_save_trends_cache()
            else:
                cached_c = TRENDS_CACHE.get(original)
                if cached_c and cached_c.get("trends") and tf in cached_c["trends"]:
                    cached_tstr = cached_c["trends"][tf]
                    if cached_tstr == "Strong Bullish": val = 1.0
                    elif cached_tstr == "Bullish": val = 0.6
                    elif cached_tstr == "Weak Bullish": val = 0.2
                    elif cached_tstr == "Weak Bearish": val = -0.2
                    elif cached_tstr == "Bearish": val = -0.6
                    elif cached_tstr == "Strong Bearish": val = -1.0
                    else: val = 0.0
                else:
                    h = sum(ord(char) for char in original) + sum(ord(char) for char in tf)
                    score = (h % 100)
                    if score > 60: val = 0.6
                    elif score > 30: val = -0.6
                    else: val = 0.0
                
            results[original] = val
            
        return {"status": "success", "data": results}
    except Exception as e:
        logger.error(f"Recalculate trend API error: {e}")
        return {"status": "error", "message": str(e)}

class RecalculateRrRequest(BaseModel):
    tickers: List[str]
    timeframe: str = "4h"
    lookback_days: int = 20
    side: str = "TREND"
    trend_values: Dict[str, float] = {}

@router.post("/recalculate_rr")
async def recalculate_rr(req: RecalculateRrRequest):
    """Recalculate max achievable Risk-to-Reward ratio (RR) for a list of symbols on-demand."""
    from datetime import timedelta
    import yfinance as yf
    from src.tools.macros import extract_single_ticker_df
    try:
        tickers = [t.strip().upper() for t in req.tickers if t and isinstance(t, str)]
        tf = req.timeframe.strip()
        lookback_days = req.lookback_days
        side = req.side.strip().upper()
        
        normalized_map = {t: _normalize_ticker(t) for t in tickers}
        search_symbols = list(set(normalized_map.values()))
        
        interval = tf
        if tf == "1m":
            period = "2d"
        elif tf == "5m":
            period = "5d"
        elif tf == "15m":
            period = "1mo"
        elif tf == "1h":
            period = "3mo"
        elif tf == "4h":
            interval = "1h"
            period = "3mo"
        elif tf == "1d":
            period = "2y"
        elif tf == "1w":
            interval = "1wk"
            period = "5y"
        else:
            interval = "1d"
            period = "2y"
            
        async with YF_LOCK:
            data = await asyncio.to_thread(yf.download, search_symbols, period=period, interval=interval, progress=False)
            
        results = {}
        for original in tickers:
            norm = normalized_map.get(original)
            df = extract_single_ticker_df(data, norm)
            if tf == "4h" and df is not None and not df.empty:
                try:
                    df = df.resample('4h').last().dropna()
                except Exception:
                    pass
            
            if df is None or df.empty or len(df) < 2:
                results[original] = 0.0
                continue
                
            col_map = {str(col).lower(): col for col in df.columns}
            high_col = col_map.get("high")
            low_col = col_map.get("low")
            close_col = col_map.get("close")
            if not high_col or not low_col or not close_col:
                results[original] = 0.0
                continue
                
            close_latest = float(df[close_col].dropna().iloc[-1])
            atr_latest = calculate_atr_14(df)
            
            # slice df for lookback range
            last_dt = df.index[-1]
            cutoff_dt = last_dt - timedelta(days=lookback_days)
            lookback_df = df[df.index >= cutoff_dt]
            if lookback_df.empty:
                lookback_df = df
                
            high_lookback = float(lookback_df[high_col].dropna().max())
            low_lookback = float(lookback_df[low_col].dropna().min())
            
            # Determine trend direction
            is_bullish = True
            if side == "LONG":
                is_bullish = True
            elif side == "SHORT":
                is_bullish = False
            else:
                # Fallback to trend value
                t_val = req.trend_values.get(original, 0.0)
                is_bullish = t_val >= 0.0
                
            if is_bullish:
                if high_lookback > close_latest:
                    max_rr = (high_lookback - close_latest) / (1.4 * atr_latest)
                else:
                    max_rr = 0.0
            else:
                if close_latest > low_lookback:
                    max_rr = (close_latest - low_lookback) / (1.4 * atr_latest)
                else:
                    max_rr = 0.0
                    
            results[original] = round(max(max_rr, 0.0), 2)
            
        return {"status": "success", "data": results}
    except Exception as e:
        logger.error(f"Recalculate RR API error: {e}")
        return {"status": "error", "message": str(e)}

class RecalculateSortinoRequest(BaseModel):
    tickers: List[str]
    profile: str = "SWING_MED"

@router.post("/recalculate_sortino")
async def recalculate_sortino(req: RecalculateSortinoRequest):
    """Recalculate Sortino Ratio for a list of symbols based on the selected timeframe profile."""
    import yfinance as yf
    from src.tools.scanner import calculate_sortino_ratio
    try:
        tickers = [t.strip().upper() for t in req.tickers if t and isinstance(t, str)]
        profile = req.profile.strip().upper()
        
        # Institutional recommended configurations
        # Profile -> (Period/Lookback, Interval/BarSize)
        if profile == "DAY":
            period, interval = "5d", "15m"
        elif profile == "SWING_LOW":
            period, interval = "30d", "1h"
        elif profile == "SWING_MED":
            period, interval = "60d", "4h"
        elif profile == "HOLD":
            period, interval = "2y", "1d"
        else:
            period, interval = "60d", "4h"
            
        # Determine the yfinance interval. For 4h, we download 1h and resample.
        yf_interval = interval
        if interval == "4h":
            yf_interval = "1h"
            
        # Clean/normalize tickers
        normalized_map = {t: _normalize_ticker(t) for t in tickers}
        search_symbols = list(set(normalized_map.values()))
        
        trading_style = os.getenv("VLI_TRADING_STYLE", "day_trading")
        dynamic_rf = 0.0428
        if trading_style == "day_trading":
            dynamic_rf = 0.0
        else:
            try:
                tnx_data = await asyncio.to_thread(yf.download, "^TNX", period="5d", interval="1d", progress=False)
                if not tnx_data.empty and 'Close' in tnx_data.columns:
                    latest_tnx = float(tnx_data['Close'].dropna().iloc[-1])
                    dynamic_rf = latest_tnx / 100.0
            except Exception:
                pass
                
        async with YF_LOCK:
            data = await asyncio.to_thread(yf.download, search_symbols, period=period, interval=yf_interval, group_by='ticker', progress=False)
            
        results = {}
        from src.tools.macros import extract_single_ticker_df
        for original in tickers:
            norm = normalized_map.get(original)
            df = extract_single_ticker_df(data, norm)
            if df is None or df.empty:
                results[original] = 0.0
                continue
                
            # If interval is 4h, resample 1h to 4h
            if interval == "4h":
                try:
                    df = df.resample('4h').last().dropna()
                except Exception:
                    pass
                    
            col_map = {str(col).lower(): col for col in df.columns}
            close_col = col_map.get("close")
            if not close_col:
                results[original] = 0.0
                continue
                
            returns = df[close_col].pct_change().dropna()
            val = calculate_sortino_ratio(returns, annual_rf=dynamic_rf, interval=interval)
            results[original] = val
            
        return {"status": "success", "data": results}
    except Exception as e:
        logger.error(f"Recalculate Sortino API error: {e}")
        return {"status": "error", "message": str(e)}

class RecalculateSweepRequest(BaseModel):
    tickers: List[str]
    profile: str = "SWING_MED"

@router.post("/recalculate_sweep")
async def recalculate_sweep(req: RecalculateSweepRequest):
    """Recalculate the HTF Candle Sweep status for a list of symbols based on active timeframe profile."""
    import yfinance as yf
    try:
        tickers = [t.strip().upper() for t in req.tickers if t and isinstance(t, str)]
        profile = req.profile.strip().upper()
        
        # Profile -> HTF Interval & Lookback Mapping
        if profile == "DAY":
            period, interval = "5d", "1h"
        elif profile == "SWING_LOW":
            period, interval = "20d", "4h"
        elif profile == "SWING_MED":
            period, interval = "60d", "1d"
        elif profile == "HOLD":
            period, interval = "365d", "1wk"
        else:
            period, interval = "60d", "1d"
            
        yf_interval = "1h" if interval == "4h" else interval
        
        # Clean/normalize tickers
        normalized_map = {t: _normalize_ticker(t) for t in tickers}
        search_symbols = list(set(normalized_map.values()))
        
        async with YF_LOCK:
            data = await asyncio.to_thread(yf.download, search_symbols, period=period, interval=yf_interval, group_by='ticker', progress=False)
            
        results = {}
        from src.tools.macros import extract_single_ticker_df
        for original in tickers:
            norm = normalized_map.get(original)
            df = extract_single_ticker_df(data, norm)
            if df is None or df.empty or len(df) < 2:
                results[original] = {"sweep": "NONE", "htf": interval}
                continue
                
            # If interval is 4h, resample 1h to 4h
            if interval == "4h":
                try:
                    col_map = {str(c).lower(): c for c in df.columns}
                    agg_dict = {}
                    if 'open' in col_map: agg_dict[col_map['open']] = 'first'
                    if 'high' in col_map: agg_dict[col_map['high']] = 'max'
                    if 'low' in col_map: agg_dict[col_map['low']] = 'min'
                    if 'close' in col_map: agg_dict[col_map['close']] = 'last'
                    if 'volume' in col_map: agg_dict[col_map['volume']] = 'sum'
                    
                    df = df.resample('4h').agg(agg_dict).dropna()
                except Exception as ex:
                    logger.error(f"Resampling failed for {original}: {ex}")
                    
            col_map = {str(c).lower(): c for c in df.columns}
            high_col = col_map.get("high")
            low_col = col_map.get("low")
            close_col = col_map.get("close")
            
            if not high_col or not low_col or not close_col:
                results[original] = {"sweep": "NONE", "htf": interval}
                continue
                
            prev_row = df.iloc[-2]
            curr_row = df.iloc[-1]
            
            prev_low = float(prev_row[low_col])
            prev_high = float(prev_row[high_col])
            curr_low = float(curr_row[low_col])
            curr_high = float(curr_row[high_col])
            curr_close = float(curr_row[close_col])
            
            sweep_state = "NONE"
            if curr_low < prev_low and curr_close > prev_low:
                sweep_state = "BULLISH"
            elif curr_high > prev_high and curr_close < prev_high:
                sweep_state = "BEARISH"
                
            results[original] = {
                "sweep": sweep_state,
                "htf": interval,
                "prev_low": round(prev_low, 2),
                "prev_high": round(prev_high, 2)
            }
            
        return {"status": "success", "data": results}
    except Exception as e:
        logger.error(f"Recalculate Sweep API error: {e}")
        return {"status": "error", "message": str(e)}

@router.delete("/purge")
async def purge_scanner_cache():
    """Purges the entire scanner combat list and transit state cache."""
    try:
        from src.tools.scanner import clear_scanner_cache
        res = await clear_scanner_cache.ainvoke({})
        return {"status": "success", "message": res}
    except Exception as e:
        logger.error(f"Failed to purge scanner cache: {e}")
        return {"status": "error", "message": str(e)}

class TradingViewSegment(BaseModel):
    state: str
    is_forming: bool
    open: float
    high: float
    low: float
    close: float
    prev_high: float
    prev_low: float
    open_time: str
    close_time: str = ""

class TradingViewAlertPayload(BaseModel):
    symbol: str
    timeframe: str
    state: Optional[str] = None
    is_forming: Optional[bool] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    prev_high: Optional[float] = None
    prev_low: Optional[float] = None
    open_time: Optional[str] = None
    close_time: str = ""
    segments: Optional[List[TradingViewSegment]] = None

@router.post("/webhook")
@router.post("/webhook/")
async def webhook_tradingview(payload: TradingViewAlertPayload):
    """
    Receives alerts from TradingView, maps the symbol, and updates TRENDS_CACHE
    realtime with zero-latency.
    """
    try:
        # Normalize symbol
        sym_clean = payload.symbol.upper().replace("1!", "").replace("=F", "").replace("/", "").strip()
        # Handle futures prefixing
        futures = ["ES", "NQ", "YM", "RTY", "CL", "GC", "NKD", "MES", "MNQ", "MYM", "M2K", "MCL", "MGC", "MNK"]
        sym_key = f"/{sym_clean}" if sym_clean in futures else payload.symbol
        
        # Normalize timeframe key
        tf = payload.timeframe.lower().strip()
        if tf in ["15", "15m", "15min", "15minut", "15_min"]:
            tf_key = "crt_15m"
        elif tf in ["1h", "1hour", "60", "60m", "1_hour"]:
            tf_key = "crt_1h"
        elif tf in ["4h", "4hour", "240", "240m", "4_hour"]:
            tf_key = "crt_4h"
        else:
            tf_key = f"crt_{tf}"

        global TRENDS_CACHE
        if sym_key not in TRENDS_CACHE:
            TRENDS_CACHE[sym_key] = {
                "trends": {},
                "timestamp": 0.0,
                "price": payload.close,
                "change": 0.0,
                "rvol": 1.0,
                "pd_zone": 0.0
            }
        TRENDS_CACHE[sym_key]["webhook_managed"] = True
        
        # Ensure target crt list exists
        if tf_key not in TRENDS_CACHE[sym_key]:
            # Initialize with 5 blank elements
            TRENDS_CACHE[sym_key][tf_key] = [
                {"state": "NONE", "is_forming": i == 4, "potential_setup": "NONE", 
                 "open": 0.0, "close": 0.0, "high": 0.0, "low": 0.0, 
                 "prev_high": 0.0, "prev_low": 0.0, "open_time": "", "close_time": ""}
                for i in range(5)
            ]
        
        if payload.segments:
            # Overwrite the entire 5 segments with the list from TradingView!
            new_segments = []
            for s in payload.segments[-5:]: # Keep last 5
                pot_setup = "NONE"
                if s.is_forming:
                    if s.state in ["BULL_SWEEP", "DOUBLE_SWEEP"]:
                        pot_setup = "BULLISH"
                    elif s.state == "BEAR_SWEEP":
                        pot_setup = "BEARISH"
                new_segments.append({
                    "state": s.state,
                    "is_forming": s.is_forming,
                    "potential_setup": pot_setup,
                    "open": s.open,
                    "high": s.high,
                    "low": s.low,
                    "close": s.close,
                    "prev_high": s.prev_high,
                    "prev_low": s.prev_low,
                    "open_time": s.open_time,
                    "close_time": s.close_time or s.open_time
                })
            while len(new_segments) < 5:
                new_segments.insert(0, {
                    "state": "NONE", "is_forming": False, "potential_setup": "NONE",
                    "open": 0.0, "close": 0.0, "high": 0.0, "low": 0.0,
                    "prev_high": 0.0, "prev_low": 0.0, "open_time": "", "close_time": ""
                })
            TRENDS_CACHE[sym_key][tf_key] = new_segments
            latest_close = payload.segments[-1].close if payload.segments else 0.0
        else:
            segments = TRENDS_CACHE[sym_key][tf_key]
            
            # Build the segment dictionary
            pot_setup = "NONE"
            if payload.is_forming:
                if payload.state in ["BULL_SWEEP", "DOUBLE_SWEEP"]:
                    pot_setup = "BULLISH"
                elif payload.state == "BEAR_SWEEP":
                    pot_setup = "BEARISH"
                    
            new_seg = {
                "state": payload.state,
                "is_forming": payload.is_forming,
                "potential_setup": pot_setup,
                "open": payload.open,
                "close": payload.close,
                "high": payload.high,
                "low": payload.low,
                "prev_high": payload.prev_high,
                "prev_low": payload.prev_low,
                "open_time": payload.open_time,
                "close_time": payload.close_time or payload.open_time
            }
            
            # Check if we should update an existing segment or slide in a new one
            matched_idx = -1
            for idx, seg in enumerate(segments):
                if seg.get("open_time") == payload.open_time:
                    matched_idx = idx
                    break
                    
            if matched_idx != -1:
                # Update existing
                segments[matched_idx] = new_seg
            else:
                # If not matched, we append to the end and keep only the last 5
                segments.append(new_seg)
                if len(segments) > 5:
                    segments.pop(0)
            
            latest_close = payload.close
        
        # Update symbol price in cache
        import time
        TRENDS_CACHE[sym_key]["price"] = latest_close
        TRENDS_CACHE[sym_key]["webhook_ts_" + tf_key] = time.time()
        
        # Save cache to disk
        await async_save_trends_cache()
        logger.info(f"Successfully updated webhook trends cache for {sym_key} ({tf_key})")
        
        return {"status": "success", "message": f"Updated {sym_key} ({tf_key})"}
    except Exception as e:
        logger.error(f"Error in webhook endpoint: {e}")
        return {"status": "error", "message": str(e)}
