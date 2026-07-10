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
from typing import Dict, Any, List
from zoneinfo import ZoneInfo
from src.tools.finance import _fetch_batch_history, _extract_ticker_data

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
            
            async with YF_LOCK:
                c_batch_1m = await asyncio.to_thread(yf.download, chunk, period="2d", interval="1m", prepost=True, progress=False)
                c_batch_5m = await asyncio.to_thread(yf.download, chunk, period="5d", interval="5m", prepost=True, progress=False)
                c_batch_15m = await asyncio.to_thread(yf.download, chunk, period="1mo", interval="15m", prepost=True, progress=False)
                c_batch_1h = await asyncio.to_thread(yf.download, chunk, period="3mo", interval="1h", prepost=True, progress=False)
                c_batch_1d = await asyncio.to_thread(yf.download, chunk, period="2y", interval="1d", progress=False)
            
            now = time.time()
            for sym in chunk:
                c_timeframes = {
                    "1m": extract_single_ticker_df(c_batch_1m, sym),
                    "5m": extract_single_ticker_df(c_batch_5m, sym),
                    "15m": extract_single_ticker_df(c_batch_15m, sym),
                    "1h": extract_single_ticker_df(c_batch_1h, sym),
                    "4h": None,
                    "1d": extract_single_ticker_df(c_batch_1d, sym)
                }
                
                df_1h = c_timeframes["1h"]
                if df_1h is not None and not df_1h.empty:
                    try:
                        c_timeframes["4h"] = df_1h.resample('4h').last().dropna()
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

                # Preserve existing cached values if the new fetch returned empty (e.g. rate limited)
                cached = TRENDS_CACHE.get(sym)
                existing_trends = cached.get("trends") if cached else None
                existing_spark_1m = cached.get("sparkline_1m") if cached else None
                existing_spark_5m = cached.get("sparkline_5m") if cached else None
                existing_spark_15m = cached.get("sparkline_15m") if cached else None
                existing_spark_1h = cached.get("sparkline_1h") if cached else None
                atr_val = calculate_atr_14(c_timeframes["1d"])
                vwap_val = calculate_vwap_state(c_timeframes["5m"], atr=atr_val)
                
                TRENDS_CACHE[sym] = {
                    "trends": trends if (trends and any(v != "No Data" for v in trends.values())) else (existing_trends or {}),
                    "sparkline_1m": spark_1m if spark_1m else (existing_spark_1m or []),
                    "sparkline_5m": spark_5m if spark_5m else (existing_spark_5m or []),
                    "sparkline_15m": spark_15m if spark_15m else (existing_spark_15m or []),
                    "sparkline_1h": spark_1h if spark_1h else (existing_spark_1h or []),
                    "vwap_state": vwap_val,
                    "price": live_price if live_price is not None else (cached.get("price") if cached else None),
                    "change": live_change if live_change is not None else (cached.get("change") if cached else None),
                    "rvol": live_rvol if live_rvol is not None else (cached.get("rvol") if cached else None),
                    "timestamp": now
                }
            
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
            for tf_name in ["1m", "5m", "15m", "1h", "4h", "1d"]:
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
                
            TRENDS_CACHE[sym] = {
                "trends": sample_trends,
                "sparkline_1m": mock_1m,
                "sparkline_5m": mock_5m,
                "sparkline_15m": mock_15m,
                "sparkline_1h": mock_1h,
                "vwap_state": 0.35 if (sum(ord(c) for c in sym) % 2 == 0) else -0.45,
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
                    "vwap_state": c.get("vwap_state", 0.0),
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
            c["vwap_state"] = TRENDS_CACHE[sym].get("vwap_state", 0.0)
            
            # Update live stats dynamically
            cached_price = TRENDS_CACHE[sym].get("price")
            cached_change = TRENDS_CACHE[sym].get("change")
            cached_rvol = TRENDS_CACHE[sym].get("rvol")
            
            if cached_price is not None:
                c["price"] = cached_price
            if cached_change is not None:
                c["change"] = cached_change
            if cached_rvol is not None:
                c["rvol"] = cached_rvol
        else:
            c["trends"] = db_trends
            c["sparkline_1m"] = c.get("sparkline_1m", []),
            c["sparkline_5m"] = c.get("sparkline_5m", []),
            c["sparkline_15m"] = c.get("sparkline_15m", []),
            c["sparkline_1h"] = c.get("sparkline_1h", []),
            c["vwap_state"] = c.get("vwap_state", 0.0)
            
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
async def scanner_stream():
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
            
            # [NEW] Calculate Sortino for Phase 0 Universe with normalization
            from src.tools.scanner import batch_fetch_sortino
            # Normalize: discard .A, .PRO, etc for yfinance
            all_symbols = [r["symbol"] for r in phase0_raw if r["symbol"]]
            normalized_map = {s: s.split(".")[0].split("-")[0] for s in all_symbols}
            search_symbols = list(set(normalized_map.values()))
            
            # Safety check: if too many symbols, yfinance might hang. We log this.
            if len(search_symbols) > 50:
                yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'High-density universe detected ({len(search_symbols)}). Phase 0 might take up to 30s...'}), cls=NpEncoder)}\n\n"

            sortino_map_norm = await batch_fetch_sortino(search_symbols)
            
            for r in phase0_raw:
                norm_s = normalized_map.get(r["symbol"])
                r["sortino"] = sortino_map_norm.get(norm_s, 0.0)

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
