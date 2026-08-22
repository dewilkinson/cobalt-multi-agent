# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Agent: Scout - Core financial primitives and data retrieval.
# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import asyncio
import logging
import threading
import time
import datetime
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import numpy as np
import yfinance

# Use curl_cffi for industrial-strength browser spoofing
from curl_cffi.requests import Session
from langchain_core.tools import tool
from src.services.datastore import DatastoreManager
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

from src.tools.shared_storage import GLOBAL_CONTEXT, SCOUT_CONTEXT, history_cache

from .scraper import fetch_finviz_quotes
from .screenshot import snapper
from src.utils.temporal import get_effective_now

# 1. Private context
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context
_SHARED_RESOURCE_CONTEXT = SCOUT_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

# 4. Specialized Analysis Cache (Isolated from Scout)
_ANALYSIS_CACHE: dict[str, Any] = {}

# [PERFORMANCE] Turn-level Raw Data Cache to prevent redundant yfinance calls in a single turn.
_RAW_DATA_CACHE: dict[str, Any] = {}
_RAW_DATA_LOCK = threading.Lock()

# Global semaphore to prevent slamming Yahoo Finance API
# We limit to 3 concurrent network requests to prevent rate limiting and head-of-line blocking.
import weakref
_YF_SEMAPHORE = weakref.WeakKeyDictionary()
_AV_SEMAPHORE = weakref.WeakKeyDictionary()

def _get_av_semaphore() -> asyncio.Semaphore:
    global _AV_SEMAPHORE
    loop = asyncio.get_running_loop()
    if loop not in _AV_SEMAPHORE:
        _AV_SEMAPHORE[loop] = asyncio.Semaphore(15)
    return _AV_SEMAPHORE[loop]

def _get_yf_semaphore() -> asyncio.Semaphore:
    """Lazy initialization of the semaphore in the correct event loop."""
    global _YF_SEMAPHORE
    loop = asyncio.get_running_loop()
    if loop not in _YF_SEMAPHORE:
        _YF_SEMAPHORE[loop] = asyncio.Semaphore(3)
    return _YF_SEMAPHORE[loop]


# Thread-local storage for sessions to avoid pickling/multiprocessing issues
_thread_local = threading.local()


def _get_session():
    """Retrieve a fresh curl_cffi session to prevent TCP connection stalling on sequential API calls."""
    session = Session(impersonate="chrome120", timeout=30.0)
    session.headers.update({"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://finance.yahoo.com/"})
    return session


# Data Integrity
# - **ABSORPTION REQUIREMENT**: Use ONLY information explicitly provided in the tool outputs.
# - **ZERO HALLUCINATION POLICY**: You are STRICTLY FORBIDDEN from creating, estimating, or "projecting" any numerical data, stock prices, or percentages that are not found in the source material.
# - If a price or metric is missing from the tool output, you MUST state "[DATA_UNAVAILABLE]" or "Price data currently out of reach" instead of providing a simulated value.
# - Never create fictional examples, hypothetical performance metrics, or imaginary scenarios.


# Datastore registration is moved to the bottom of the file to prevent circular imports


def _normalize_ticker(ticker: str) -> str:
    """Consistently maps common tickers to their Yahoo Finance equivalents."""
    # Strip any existing index markers or futures slashes to prevent double-normalization
    t = ticker.upper().strip().lstrip("^/")
    
    if t == "VIX":
        return "^VIX"
    if t == "SPX":
        return "^GSPC"
    if t == "NDX":
        return "^NDX"
    if t == "DXY":
        return "DX-Y.NYB"
    if t == "TNX":
        return "^TNX"
    if t == "TYX":
        return "^TYX"
    if t == "FVX":
        return "^FVX"
    if t == "BTC" or t == "BTCUSDT" or t == "BT":
        return "BTC-USD"
    if t == "ETH" or t == "ETHUSDT" or t == "ET":
        return "ETH-USD"
    if t.endswith("USDT"):
        return t.replace("USDT", "-USD")
    if t == "GC" or t == "GOLD":
        return "GC=F"
    if t == "SI" or t == "SILVER":
        return "SI=F"
    if t == "WTI" or t == "CRUDE" or t == "OIL":
        return "CL=F"
    if t == "EURUSD" or t == "EUR/USD":
        return "EURUSD=X"
    if t == "GBPUSD" or t == "GBP/USD":
        return "GBPUSD=X"

    # Handle S&P 100 / Common Discrepancies (Dots to Hyphens)
    # e.g., BRK.B -> BRK-B, BF.B -> BF-B
    # EXCLUSION: DX-Y.NYB requires the dot to be preserved
    if t.upper() in ["MGC", "MGC1!", "/MGC", "MGCZ2026", "MGCZ26", "/MGCZ2026", "/MGCZ26"]:
        return "MGCZ26.CMX"

    if t in ["ES", "MES", "NQ", "MNQ", "YM", "MYM", "RTY", "M2K", "CL", "MCL", "GC", "NKD", "MNK"]:
        return t + "=F"

    return t


def _bucket_sparkline_data(df: pd.DataFrame, ref_time: datetime, current_price: float, num_points: int = 20, span_minutes: int = 390, session_mode: bool = False, step_minutes: int = 5) -> list[float | dict[str, Any] | None]:
    """
    High-Fidelity Resampling: Uses row-index interpolation or rolling active session windowing.
    """
    if df.empty:
        if session_mode:
            return [{"v": round(current_price, 4), "is_prev": False}] * num_points
        return [round(current_price, 4)] * num_points

    col = "Close" if "Close" in df.columns else "close"
    
    # Check for duplicated columns safely
    target_data = df[col]
    if isinstance(target_data, pd.DataFrame):
        target_data = target_data.iloc[:, 0]
        
    # Crucial Fix: Drop NaN values that leak from multi-ticker batch unions
    target_data = target_data.dropna().sort_index()
    
    if target_data.empty:
        if session_mode:
            return [{"v": round(current_price, 4), "is_prev": False}] * num_points
        return [round(current_price, 4)] * num_points

    if session_mode:
        # Align ref_time timezone to NY
        ref_time_ts = pd.Timestamp(ref_time)
        if ref_time_ts.tz is not None:
            ref_time_naive = ref_time_ts.tz_convert('America/New_York').tz_localize(None)
        else:
            ref_time_naive = ref_time_ts

        # Generate a list of naive NY datetimes going back in time spanning exactly 24 hours (1440 minutes)
        # step_mins is dynamically calculated to span 24 hours (1440 mins) over num_points
        step_mins = (24.0 * 60.0) / float(num_points - 1)
        
        # Identify target date based on the latest available row's date
        latest_row_time = target_data.index[-1]
        cutoff_dt = ref_time_naive

        # Anchor cutoff to the latest available data if it stopped trading before cutoff_dt
        if latest_row_time < cutoff_dt:
            cutoff_dt = latest_row_time

        dts = []
        curr = cutoff_dt

        while len(dts) < num_points:
            # Skip weekends: shift to Friday at the same time of day
            if curr.weekday() >= 5: # 5 = Saturday, 6 = Sunday
                days_to_subtract = 1 if curr.weekday() == 5 else 2
                curr -= timedelta(days=days_to_subtract)
                continue

            dts.append(curr)
            curr -= timedelta(minutes=step_mins)

        dts.reverse()

        # Sample prices at each index
        output_values = []
        for i, dt in enumerate(dts):
            # Check if this point is in the previous day relative to latest date in the 24h span
            latest_date_in_span = dts[-1].date()
            is_prev = dt.date() < latest_date_in_span

            if i == num_points - 1:
                # Last slot is always the current real-time price
                output_values.append({"v": round(float(current_price), 4), "is_prev": is_prev})
            else:
                try:
                    if hasattr(target_data.index, "unit"):
                        val = target_data.asof(pd.Timestamp(dt).as_unit(target_data.index.unit))
                    else:
                        val = target_data.asof(pd.Timestamp(dt))
                except Exception:
                    try:
                        val = target_data.asof(pd.Timestamp(dt))
                    except Exception:
                        val = target_data.asof(dt)
                if pd.isna(val):
                    output_values.append(None)
                else:
                    output_values.append({"v": round(float(val), 4), "is_prev": is_prev})

        return output_values

    # Obtain the most recent `span_minutes` rows (equivalent to last 6.5 hours of active trading since 1 row = 1 min).
    # If the history is less than span_minutes, it uses whatever is valid.
    recent_data = target_data.tail(span_minutes)
    
    # Use numpy.linspace to grab exactly `num_points` spanning the rows evenly.
    # This natively ignores all overnight/weekend gaps.
    indices = np.linspace(0, len(recent_data) - 1, num_points, dtype=int)
    values = recent_data.iloc[indices].tolist()
    
    # Ensure current_price caps the array so the sparkline resolves to the exact real-time boundary.
    output_values = [round(float(v), 4) for v in values]
    output_values[-1] = round(float(current_price), 4)
    
    return output_values


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_av_history(ticker: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    import os
    import httpx
    from io import StringIO
    
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    if not api_key:
        raise ValueError("[STABILITY] ALPHA_VANTAGE_API_KEY is not defined in the environment!")
        
    mapped_interval = interval
    endpoint = "TIME_SERIES_DAILY_ADJUSTED"
    
    if interval in ["1m", "5m", "15m", "30m", "60m"]:
        mapped_interval = interval.replace("m", "min")
        endpoint = "TIME_SERIES_INTRADAY"
        
    url = f"https://www.alphavantage.co/query?function={endpoint}&symbol={ticker}&datatype=csv&entitlement=realtime&apikey={api_key}"
    
    if endpoint == "TIME_SERIES_INTRADAY":
        url += f"&interval={mapped_interval}&outputsize=full"
    else:
        if period in ["1y", "2y", "5y", "10y", "max", "ytd"]:
             url += "&outputsize=full"
             
    try:
        resp = httpx.get(url, timeout=20.0)
        resp.raise_for_status()
        
        if "Error Message" in resp.text or "Information" in resp.text:
            logger.error(f"[AV_FETCH] API Error for {ticker}: {resp.text[:100]}")
            raise RuntimeError("Alpha Vantage Rate Limit or API Error")
            
        df = pd.read_csv(StringIO(resp.text))
        if df.empty or 'timestamp' not in df.columns:
            return pd.DataFrame()
            
        df = df[::-1].reset_index(drop=True)
        
        col_map = {
            "timestamp": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        }
        df.rename(columns=col_map, inplace=True)
        
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            
        return df
    except Exception as e:
        logger.error(f"[AV_FETCH] Critical failure parsing CSV for {ticker}: {e}")
        raise e

def _fetch_batch_history(tickers: list[str], period: str = "5d", interval: str = "1d", force_yf: bool = False) -> pd.DataFrame:
    """
    Centralized batched fetcher.
    Dynamically routes to Alpha Vantage concurrent pipeline OR YFinance fallback pipeline.
    """
    logger.info(f"Executing batched fetch for {tickers} (p={period}, i={interval})")
    
    # [UNIVERSAL_TEMPORAL_INSTRUMENTATION]
    from src.utils.temporal import get_effective_now
    ref_time = get_effective_now()
    now = datetime.now()
    
    # Check if we are in Replay mode
    is_replay = abs((now - ref_time).total_seconds()) > 5
    
    mapped_tickers = [_normalize_ticker(t) for t in tickers]
    # Cache key includes the temporal origin if in replay mode
    temporal_suffix = f"_{ref_time.isoformat()}" if is_replay else ""
    cache_key = f"{','.join(sorted(mapped_tickers))}_{period}_{interval}{temporal_suffix}"
    
    with _RAW_DATA_LOCK:
        if cache_key in _RAW_DATA_CACHE:
            cached_data, timestamp = _RAW_DATA_CACHE[cache_key]
            # [REPLAY_STABILITY] Replay data is cached for the entire session (3600s), 
            # Real-time data for 60s.
            ttl = 3600 if is_replay else 60
            if (datetime.now() - timestamp).total_seconds() < ttl:
                logger.debug(f"[RAW_CACHE_HIT] Reusing data for {mapped_tickers} ({period}/{interval})")
                return cached_data

    import os
    provider = "yfinance" if force_yf else os.environ.get("DATA_PROVIDER", "yfinance").lower()

    if is_replay:
        logger.info(f"VLI_REPLAY: Universal delegation for {tickers} (Target Origin: {ref_time})")
        data = _fetch_replay_history(tickers, period, interval, end_date=ref_time)
    elif provider == "alpha_vantage":
        logger.info(f"[AV PARALLEL ENGINE] Extracting {len(mapped_tickers)} tickers concurrently via Alpha Vantage")
        
        async def fetch_av_concurrently(index, t):
            await asyncio.sleep(0.25 * index)  # Stagger requests to avoid burst rate limits
            async with _get_av_semaphore():
                try:
                    df = await asyncio.to_thread(_fetch_av_history, t, period, interval)
                    return t, df
                except Exception as e:
                    logger.error(f"[AV PARALLEL ENGINE] Task failed for {t}: {e}")
                    return t, pd.DataFrame()

        async def run_tasks():
            tasks = [fetch_av_concurrently(i, t) for i, t in enumerate(mapped_tickers)]
            return await asyncio.gather(*tasks)
            
        try:
            results = asyncio.run(run_tasks())
        except RuntimeError:
            import nest_asyncio
            nest_asyncio.apply()
            results = asyncio.get_event_loop().run_until_complete(run_tasks())

        master_dict = {}
        failed_tickers = []
        for t, df in results:
            if not df.empty:
                for col in df.columns:
                    master_dict[(col, t)] = df[col]
            else:
                failed_tickers.append(t)

        if failed_tickers:
            logger.warning(f"[AV PARALLEL ENGINE] {len(failed_tickers)} tickers failed via Alpha Vantage. Falling back to YFinance for: {failed_tickers}")
            try:
                @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=6))
                def _do_yf_fallback():
                    return yfinance.download(
                        tickers=failed_tickers,
                        period=period,
                        interval=interval,
                        group_by="ticker",
                        session=_get_session(),
                        progress=False,
                        threads=False,
                        timeout=15.0,
                        auto_adjust=False,
                        prepost=True,
                    )
                yf_data = _do_yf_fallback()
                if yf_data is not None and not yf_data.empty:
                    if isinstance(yf_data.columns, pd.MultiIndex):
                        for col in yf_data.columns:
                            part1, part2 = str(col[0]), str(col[1])
                            if part1 in failed_tickers:
                                master_dict[(part2, part1)] = yf_data[col]
                            elif part2 in failed_tickers:
                                master_dict[(part1, part2)] = yf_data[col]
                    elif len(failed_tickers) == 1:
                        t = failed_tickers[0]
                        for col in yf_data.columns:
                            master_dict[(col, t)] = yf_data[col]
            except Exception as yfe:
                logger.error(f"[AV FALLBACK] YFinance download failed for {failed_tickers}: {yfe}")
        # Standardize all indices to tz-naive to prevent TypeError: Cannot join tz-naive with tz-aware DatetimeIndex
        for key in list(master_dict.keys()):
            series = master_dict[key]
            if series is not None and hasattr(series, 'index') and series.index is not None:
                if getattr(series.index, 'tz', None) is not None:
                    s = series.copy()
                    try:
                        s.index = s.index.tz_convert('America/New_York').tz_localize(None)
                    except Exception:
                        s.index = s.index.tz_localize(None)
                    master_dict[key] = s
                    
        data = pd.DataFrame(master_dict) if master_dict else pd.DataFrame()
    else:
        logger.debug(f"[WEB REQUEST] Yahoo Finance fetching {len(mapped_tickers)} tickers: {mapped_tickers}")
        start_time = time.time()
        try:
            @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
            def _do_yf_download():
                return yfinance.download(
                    tickers=mapped_tickers,
                    period=period,
                    interval=interval,
                    group_by="ticker",
                    session=_get_session(),
                    progress=False,
                    threads=False,
                    timeout=20.0,
                    auto_adjust=False,
                    prepost=True,
                )
            data = _do_yf_download()
            duration_ms = (time.time() - start_time) * 1000
            if data is not None and not data.empty:
                logger.debug(f"[WEB RESPONSE] Yahoo Finance fetch successful in {duration_ms:.2f}ms for {mapped_tickers}")
            else:
                logger.warning(f"[WEB RESPONSE] Empty data for {mapped_tickers}")
        except Exception as e:
            logger.error(f"[ERROR] Yahoo Finance fetch failed: {e}")
            raise

    # Store in cache after fetch
    if data is not None and not data.empty:
        with _RAW_DATA_LOCK:
            _RAW_DATA_CACHE[cache_key] = (data, datetime.now())
            
    return data


def _fetch_replay_history(tickers: list[str], period: str = "5d", interval: str = "1d", end_date: datetime = None) -> pd.DataFrame:
    """
    Sub-fetcher for Replay Engine which forces a sliding window relative to a historical origin.
    Automatically downsamples intervals if the origin is too old (e.g. 1m data limited to last 30 days).
    """
    # 1. Adaptive Downsampling
    now = datetime.now()
    if end_date and (now - end_date).days > 29:
        if interval in ["1m", "2m", "5m"]:
            logger.info(f"VLI_REPLAY: Auto-downsampling interval from {interval} to 1d (Origin > 30 days old)")
            interval = "1d"
        elif interval in ["15m", "30m", "60m", "1h"]:
            logger.info(f"VLI_REPLAY: Auto-downsampling interval from {interval} to 1d (Origin > 730 days limit for 1h)")
            if (now - end_date).days > 720:
                interval = "1d"

    logger.info(f"VLI_REPLAY: Fetching {tickers} (p={period}, i={interval}) ending at {end_date}")
    mapped_tickers = [_normalize_ticker(t) for t in tickers]
    
    # Calculate start_date if period is given (approximate)
    # yfinance handles 'period' internally if 'end' is provided, but 'start' is safer for specific windows
    # Actually yfinance 0.2.x handles start/end well.
    
    # ... (rest of function unchanged, but removing blocking sleep if any)
    start_time = time.time()
    try:
        data = yfinance.download(
            tickers=mapped_tickers,
            period=period,
            end=end_date,
            interval=interval,
            group_by="ticker",
            session=_get_session(),
            progress=False,
            threads=False,
            timeout=20.0,    # [HARDEN]
            auto_adjust=False, # [SPLIT_AWARENESS] Maintain nominal scale for reporting
        )
        duration_ms = (time.time() - start_time) * 1000
        logger.debug(f"VLI_REPLAY: fetch successful in {duration_ms:.2f}ms")
        return data
    except Exception as e:
        logger.error(f"VLI_REPLAY: fetch failed: {e}")
        raise


def _extract_ticker_data(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Helper to extract a single ticker's dataframe from a multi-index yf.download result.
    Will automatically try normalized ticker names if the original key is not present.
    """
    ticker_upper = ticker.upper()
    norm_ticker = _normalize_ticker(ticker)

    print(f"DEBUG _extract_ticker_data: ticker={ticker}, ticker_upper={ticker_upper}, is_multi={isinstance(df.columns, pd.MultiIndex)}, df.columns={type(df.columns)}")

    res = pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        # 1. Try original ticker
        if ticker_upper in df.columns.levels[0]:
            res = df[ticker_upper].dropna(how="all").copy()
        elif len(df.columns.levels) > 1 and ticker_upper in df.columns.levels[1]:
            res = df.xs(ticker_upper, level=1, axis=1).dropna(how="all").copy()
        # 2. Try normalized ticker (VIX -> ^VIX)
        elif norm_ticker in df.columns.levels[0]:
            res = df[norm_ticker].dropna(how="all").copy()
        elif len(df.columns.levels) > 1 and norm_ticker in df.columns.levels[1]:
            res = df.xs(norm_ticker, level=1, axis=1).dropna(how="all").copy()
        else:
            try:
                res = df[ticker_upper].dropna(how="all").copy()
            except Exception:
                try:
                    res = df[norm_ticker].dropna(how="all").copy()
                except Exception:
                    res = pd.DataFrame()
    else:
        res = df.dropna(how="all").copy()

    if isinstance(res, pd.DataFrame) and not res.empty:
        new_cols = []
        for col in res.columns:
            if isinstance(col, tuple):
                new_cols.append(col[-1])
            else:
                new_cols.append(col)
        res.columns = new_cols

    return res


def _get_ttl_seconds(interval: str) -> int:
    """Helper to determine cache TTL in seconds based on interval granularity."""
    i = interval.lower()
    if i in ["1m"]:
        return 60
    if i in ["2m"]:
        return 120
    if i in ["5m"]:
        return 300
    if i in ["15m"]:
        return 900
    if i in ["30m"]:
        return 1800
    if i in ["1h", "60m"]:
        return 3600
    if i in ["2h", "4h"]:
        return 3600 * 2
    if i in ["1d", "1wk", "1mo"]:
        return 86400  # EOD cache for macro bounds
    return 300  # default 5m


def _get_active_prepost_price(ticker: str) -> dict | None:
    try:
        import yfinance
        df = yfinance.download(
            tickers=[ticker],
            period="1d",
            interval="1m",
            group_by="ticker",
            session=_get_session(),
            progress=False,
            threads=False,
            timeout=5.0,
            auto_adjust=False,
            prepost=True
        )
        if df is not None and not df.empty:
            ticker_df = _extract_ticker_data(df, ticker)
            if not ticker_df.empty:
                last_row = ticker_df.dropna(subset=["Close"]).iloc[-1]
                return {
                    "price": float(last_row["Close"]),
                    "volume": int(last_row["Volume"]),
                    "high": float(last_row["High"]) if "High" in last_row else float(last_row["Close"]),
                    "low": float(last_row["Low"]) if "Low" in last_row else float(last_row["Close"]),
                    "open": float(last_row["Open"]) if "Open" in last_row else float(last_row["Close"]),
                }
    except Exception as e:
        logger.warning(f"Failed to fetch active pre/post price for {ticker}: {e}")
    return None


def _inject_prepost_price_to_df(df: pd.DataFrame, ticker: str, interval: str) -> pd.DataFrame:
    if df is None or df.empty:
        return df
        
    import pytz
    from datetime import datetime
    est = pytz.timezone('America/New_York')
    now_est = datetime.now(est)
    is_closed = now_est.weekday() >= 5 or now_est.time() < __import__('datetime').time(9, 30) or now_est.time() >= __import__('datetime').time(16, 0)
    
    if not is_closed:
        return df
        
    logger.info(f"Market closed. Resolving active pre/post price for {ticker} (interval={interval})...")
    quote_info = _get_active_prepost_price(ticker)
    if not quote_info:
        logger.warning(f"Could not resolve active pre/post price for {ticker}")
        return df
        
    price = quote_info["price"]
    volume = quote_info["volume"]
    o_val = quote_info["open"]
    h_val = quote_info["high"]
    l_val = quote_info["low"]
    
    col_map = {col.lower(): col for col in df.columns}
    close_col = col_map.get("close")
    open_col = col_map.get("open")
    high_col = col_map.get("high")
    low_col = col_map.get("low")
    vol_col = col_map.get("volume")
    adj_col = col_map.get("adj close")
    
    if not close_col:
        return df
        
    if interval == "1d":
        today_date = now_est.date()
        idx_dates = [ts.date() for ts in df.index] if hasattr(df.index, 'date') else []
        if today_date in idx_dates:
            exact_ts = df.index[idx_dates.index(today_date)]
            df.loc[exact_ts, close_col] = price
            if open_col: df.loc[exact_ts, open_col] = o_val
            if high_col: df.loc[exact_ts, high_col] = h_val
            if low_col: df.loc[exact_ts, low_col] = l_val
            if vol_col: df.loc[exact_ts, vol_col] = volume
            if adj_col: df.loc[exact_ts, adj_col] = price
            logger.info(f"Updated daily row {exact_ts} with pre/post price {price}")
        else:
            if hasattr(df.index, 'tz') and df.index.tz is not None:
                new_ts = pd.Timestamp(today_date).tz_localize('UTC').tz_convert(df.index.tz)
            else:
                new_ts = pd.Timestamp(today_date)
                
            new_row = pd.Series(index=df.columns, dtype=float)
            new_row[close_col] = price
            if open_col: new_row[open_col] = o_val
            if high_col: new_row[high_col] = h_val
            if low_col: new_row[low_col] = l_val
            if vol_col: new_row[vol_col] = volume
            if adj_col: new_row[adj_col] = price
            
            df.loc[new_ts] = new_row
            logger.info(f"Appended new daily row {new_ts} with pre/post price {price}")
            
    elif interval in ["5m", "15m", "1h", "60m"]:
        last_idx = df.index[-1]
        df.loc[last_idx, close_col] = price
        if adj_col:
            df.loc[last_idx, adj_col] = price
        logger.info(f"Updated last intraday bar {last_idx} close with pre/post price {price}")
        
    return df


def _slice_df_to_period(df: pd.DataFrame, period: str, interval: str) -> pd.DataFrame:
    """Slices the DataFrame to match the requested lookback period exactly."""
    if df.empty:
        return df

    import re
    period_lower = period.lower().strip()
    
    # 1. Check for standard days format (e.g. "60d", "5d", "1d")
    match_d = re.match(r"^(\d+)d$", period_lower)
    if match_d:
        n_days = int(match_d.group(1))
        if interval == "1d":
            return df.tail(n_days)
        else:
            try:
                unique_dates = pd.to_datetime(df.index).date
                last_n_dates = sorted(list(set(unique_dates)))[-n_days:]
                return df[pd.Series(unique_dates).isin(last_n_dates).values]
            except Exception as e:
                logger.warning(f"Failed to slice intraday DataFrame by {n_days} calendar days: {e}")
                return df

    # 2. Check for months format (e.g. "1mo", "3mo")
    match_mo = re.match(r"^(\d+)mo$", period_lower)
    if match_mo:
        n_months = int(match_mo.group(1))
        # 1 month is roughly 21 trading days
        n_days = n_months * 21
        if interval == "1d":
            return df.tail(n_days)
        else:
            try:
                unique_dates = pd.to_datetime(df.index).date
                last_n_dates = sorted(list(set(unique_dates)))[-n_days:]
                return df[pd.Series(unique_dates).isin(last_n_dates).values]
            except Exception as e:
                logger.warning(f"Failed to slice intraday DataFrame by {n_months} months: {e}")
                return df

    # 3. Check for years format (e.g. "1y", "2y")
    match_y = re.match(r"^(\d+)y$", period_lower)
    if match_y:
        n_years = int(match_y.group(1))
        # 1 year is roughly 252 trading days
        n_days = n_years * 252
        if interval == "1d":
            return df.tail(n_days)
        else:
            try:
                unique_dates = pd.to_datetime(df.index).date
                last_n_dates = sorted(list(set(unique_dates)))[-n_days:]
                return df[pd.Series(unique_dates).isin(last_n_dates).values]
            except Exception as e:
                logger.warning(f"Failed to slice intraday DataFrame by {n_years} years: {e}")
                return df

    return df


def _fetch_stock_history(ticker: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """
    Standard single-ticker fetcher. Automatically flattens MultiIndex for the requested ticker.
    Used by all analysis nodes (Analyst, SMC, EMA, etc.). Heavily cached to prevent LangGraph sequential redundant fetching.
    """
    norm_ticker = _normalize_ticker(ticker)
    from src.utils.temporal import get_cache_segment_suffix
    suffix = get_cache_segment_suffix()
    cache_key = f"{norm_ticker}{suffix}_{period}_{interval}"

    df_cache = DatastoreManager.get_df_cache()

    if cache_key in df_cache:
        entry = df_cache[cache_key]
        if "last_updated" in entry and "df" in entry:
            age_sec = (datetime.now() - entry["last_updated"]).total_seconds()
            ttl = _get_ttl_seconds(interval)
            if age_sec < ttl:
                logger.info(f"[DF_CACHE HIT] Reusing {norm_ticker} data (Age: {age_sec:.1f}s / TTL: {ttl}s)")
                return entry["df"].copy()
            else:
                logger.info(f"[DF_CACHE EXPIRED] Ticker {norm_ticker} data is {age_sec:.1f}s old (TTL: {ttl}s)")

    data = _fetch_batch_history([ticker], period, interval)
    df = _extract_ticker_data(data, ticker)

    # Slice to exact period lookback before caching and returning
    df = _slice_df_to_period(df, period, interval)

    try:
        from src.utils.temporal import get_effective_now
        is_replay = abs((datetime.now() - get_effective_now()).total_seconds()) > 5
        if not is_replay:
            df = _inject_prepost_price_to_df(df, norm_ticker, interval)
    except Exception as e:
        logger.warning(f"Failed to inject pre/post price to history DataFrame: {e}")

    df_cache[cache_key] = {"df": df.copy(), "last_updated": datetime.now()}
    return df.copy()


def _fetch_stock_history_vli(ticker: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """Consolidated history fetcher with universal Replay and Cache support."""
    return _fetch_stock_history(ticker, period, interval)


@tool
async def get_symbol_history_data(symbols: list[str], period: str = "1d", interval: str = "1h", verbosity: int = 1, is_test_mode: bool = False) -> str:
    """
    Scout Primitive: Retrieve stock history for multiple symbols in a single batched request.
    Verbosity levels: 1 (Report only), 2 (Include fetch traces).
    """
    from datetime import datetime

    from src.config.loader import get_int_env

    expiry_minutes = get_int_env("CACHE_EXPIRY_MINUTES", 15)
    DatastoreManager.ensure_worker_started()

    logger.info(f"Scout fetching history for {symbols}")

    # Datastore cache bridge
    history_cache = DatastoreManager.get_history_cache()
    # Tracker removed

    now = datetime.now()
    results = []
    missing_symbols = []
    symbols_upper = [s.upper() for s in symbols]

    for sym in symbols:
        sym = sym.upper()
        # No heat tracking for Scout

        # Refactor Phase 2: Use DatastoreManager.get_artifact
        cached_entry = DatastoreManager.get_artifact(sym, "history", interval)
        
        is_stale = True
        if cached_entry and "updated_at" in cached_entry:
            age_min = (now - cached_entry["updated_at"]).total_seconds() / 60.0
            if age_min <= expiry_minutes:
                is_stale = False

        if not is_stale:
            logger.info(f"[CACHE_READ] Using warm lazy cache for {sym}")
            data_val = cached_entry["data"]
            if isinstance(data_val, dict) and "data" in data_val:
                results.append(data_val["data"])
            else:
                results.append(data_val)
        else:
            if cached_entry:
                logger.info(f"[CACHE_EVICT] Data for {sym} is stale. Fetching fresh data.")
            missing_symbols.append(sym)

    if missing_symbols:
        # Diagnostic check for mocks
        mocks = [s for s in missing_symbols if s.startswith(("HIGH_", "MOD_", "INACT_"))]
        others = [s for s in missing_symbols if s not in mocks]

        for m in mocks:
            results.append(f"### {m}\n- [MOCK DATA]: {m} retrieved from diagnostic seed.")

        if others:
            try:
                # Use semaphore for throttling
                async with _get_yf_semaphore():
                    # [REPLAY_INSTRUMENTATION] Check for temporal shift
                    ref_time = get_effective_now()
                    is_replay = (ref_time.date() < datetime.now().date())
                    
                    if is_replay:
                        full_df = await asyncio.wait_for(asyncio.to_thread(_fetch_replay_history, others, period, interval, end_date=ref_time), timeout=15.0)
                    else:
                        full_df = await asyncio.wait_for(asyncio.to_thread(_fetch_batch_history, others, period, interval), timeout=15.0)

                for sym in others:
                    ticker_df = _extract_ticker_data(full_df, sym)
                    if not ticker_df.empty:
                        try:
                            ticker_df = _inject_prepost_price_to_df(ticker_df, sym, interval)
                        except Exception as e:
                            logger.warning(f"Failed to inject pre/post price in get_symbol_history_data: {e}")
                    if ticker_df.empty:
                        # Fallback to Finviz
                        try:
                            from src.config.vli import write_api_telemetry
                            provider_name = "Alpha Vantage" if os.environ.get("DATA_PROVIDER", "yfinance").lower() == "alpha_vantage" else "Yahoo Finance"
                            write_api_telemetry(provider_name, False, f"Missing data for {sym}", fallback="Finviz Scraper")
                        except Exception: pass
                        try:
                            f_data = await fetch_finviz_quotes([sym])
                            if sym.upper() in f_data:
                                q = f_data[sym.upper()]
                                data_str = f"### {sym}\n- **Price**: {q['price']:.2f}\n- **Volume**: {q['volume']:,}\n- **Source**: Finviz (Fallback)"
                                results.append(data_str)
                                # Refactor Phase 2/3: Store with current price for drift check
                                DatastoreManager.store_artifact(sym, "history", interval, data_str, price=float(q["price"]))
                                continue
                        except:
                            pass
                        results.append(f"### {sym}\n- [ERROR]: Data retrieval failed.")
                        continue

                    last_row = ticker_df.iloc[-1]
                    # Ensure full OHLCV and Symbol are cached together in shared memory
                    raw_ohlcv = {
                        "Symbol": sym,
                        "Open": float(last_row.get("Open", 0)),
                        "High": float(last_row.get("High", 0)),
                        "Low": float(last_row.get("Low", 0)),
                        "Close": float(last_row.get("Close", 0)),
                        "Volume": int(last_row.get("Volume", 0)),
                    }
                    data_str = f"### {sym}\n- **Period**: {period} | **Interval**: {interval}\n- **Open**: {raw_ohlcv['Open']:.2f}\n- **High**: {raw_ohlcv['High']:.2f}\n- **Low**: {raw_ohlcv['Low']:.2f}\n- **Close**: {raw_ohlcv['Close']:.2f}\n- **Volume**: {raw_ohlcv['Volume']:,}\n"

                    # Refactor Phase 2/3: Store with current price for drift check
                    current_price = raw_ohlcv["Close"]
                    DatastoreManager.store_artifact(sym, "history", interval, {"data": data_str, "raw": raw_ohlcv}, price=current_price)
                    results.append(data_str)
                    
                    try:
                        from src.config.vli import write_api_telemetry
                        provider_name = "Alpha Vantage" if os.environ.get("DATA_PROVIDER", "yfinance").lower() == "alpha_vantage" else "Yahoo Finance"
                        write_api_telemetry(provider_name, True, f"Successfully retrieved {sym} ({interval})")
                    except Exception: pass
            except TimeoutError:
                logger.error(f"Timeout: Fetch for {others} timed out.")
                try:
                    from src.config.vli import write_api_telemetry
                    provider_name = "Alpha Vantage" if os.environ.get("DATA_PROVIDER", "yfinance").lower() == "alpha_vantage" else "Yahoo Finance"
                    write_api_telemetry(provider_name, False, f"Timeout on {others}", fallback="None")
                except Exception: pass
                results.append(f"### {others}\n- [ERROR]: Timeout during data retrieval.")
            except Exception as e:
                logger.error(f"Fetch error: {e}")
                try:
                    from src.config.vli import write_api_telemetry
                    provider_name = "Alpha Vantage" if os.environ.get("DATA_PROVIDER", "yfinance").lower() == "alpha_vantage" else "Yahoo Finance"
                    write_api_telemetry(provider_name, False, f"Error: {str(e)[:50]}", fallback="None")
                except Exception: pass
                results.append(f"### {others}\n- [ERROR]: {str(e)}")

    report = f"# Stock History Report\nGenerated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    report += "\n".join([str(r) for r in results])
    return report.strip()


@tool
async def simulate_cache_volatility(num_high: int = 10, num_moderate: int = 30, num_inactive: int = 10) -> str:
    """
    Scout Primitive (Diagnostic): Artificially populates the global cache with mock tickers of varying usage 'heat' to test eager/lazy architecture.
    """
    from datetime import datetime, timedelta

    ticker_metadata = _GLOBAL_RESOURCE_CONTEXT.setdefault("ticker_metadata", {})
    history_cache = DatastoreManager.get_history_cache()
    cached_tickers_set = _GLOBAL_RESOURCE_CONTEXT.setdefault("cached_tickers", set())

    now = datetime.now()
    stale_time = now - timedelta(seconds=10)  # Immediately push past 5s boundary

    # 10 High Activity
    for i in range(num_high):
        sym = f"HIGH_{i}"
        ticker_metadata[sym] = {"heat": 100}
        from src.services.heat_manager import HeatManager
        # Force high heat in new Manager
        HeatManager.increment_heat(sym, 100.0)
        DatastoreManager.store_artifact(sym, "history", "1h", f"### {sym}\nMock high heat", price=100.0)
        cached_tickers_set.add(sym)

    # 30 Moderate Activity
    for i in range(num_moderate):
        sym = f"MOD_{i}"
        ticker_metadata[sym] = {"heat": 10}
        HeatManager.increment_heat(sym, 10.0)
        DatastoreManager.store_artifact(sym, "history", "1h", f"### {sym}\nMock mod heat", price=100.0)
        cached_tickers_set.add(sym)

    # 10 Inactive
    for i in range(num_inactive):
        sym = f"INACT_{i}"
        ticker_metadata[sym] = {"heat": 1}
        HeatManager.increment_heat(sym, 1.0)
        DatastoreManager.store_artifact(sym, "history", "1h", f"### {sym}\nMock inactive", price=100.0)
        cached_tickers_set.add(sym)

    # Simulate random clicks to reach final distribution
    import random

    mock_tickers = [f"HIGH_{i}" for i in range(num_high)] + [f"MOD_{i}" for i in range(num_moderate)] + [f"INACT_{i}" for i in range(num_inactive)]

    # We want HIGH tickers to have lots of hits (bar visualization)
    for sym in mock_tickers:
        meta = ticker_metadata[sym]
        if sym.startswith("HIGH_"):
            meta["heat"] = random.randint(25, 45)
        elif sym.startswith("MOD_"):
            meta["heat"] = random.randint(8, 18)
        else:
            meta["heat"] = random.randint(1, 3)

    logger.info(f"[CACHE_DIAGNOSTIC] Generated distribution: {num_high} high, {num_moderate} moderate, {num_inactive} inactive.")
    return "Successfully populated 50 mock stocks with distribution 10/30/10. Visual Heat Map is now available."


@tool
async def get_cache_heat_map() -> str:
    """
    System Admin Tool: Generates a high-fidelity visual representation of the current cache 'heat' distribution.
    Shows frequency counters using bar visualizations and color-coded health states.
    """
    ticker_metadata = _GLOBAL_RESOURCE_CONTEXT.get("ticker_metadata", {})
    if not ticker_metadata:
        return "Cache is currently empty."

    sorted_tickers = sorted(ticker_metadata.keys(), key=lambda s: ticker_metadata[s].get("heat", 0), reverse=True)

    lines = ["# VLI Hybrid Cache Heat Map", ""]
    lines.append("| Ticker | Heat Level | Activity Bar | Status |")
    lines.append("| :--- | :--- | :--- | :--- |")

    for sym in sorted_tickers:
        heat = ticker_metadata[sym].get("heat", 0)

        # Determine Color/Category
        if heat >= 25:
            status = " **Top 5**" if sorted_tickers.index(sym) < 5 else " **Top 10**"
            bar_char = "█"
        elif heat >= 8:
            status = " **Active**"
            bar_char = "▓"
        elif heat >= 4:
            status = " **Lazy**"
            bar_char = "▒"
        else:
            status = " **Evictable**"
            bar_char = "░"

        bar = bar_char * min(heat, 20)  # Cap bar length for UI
        if heat > 20:
            bar += "+"

        lines.append(f"| {sym} | {heat} | `{bar}` | {status} |")

    return "\n".join([str(l) for l in lines])


@tool
async def vli_cache_tick(iteration: int) -> str:
    """
    VLI System Diagnostic (Heartbeat): Executes a single iterative tick of the VLI autonomic cache simulation.
    Handles symbol arrival, heat decay, and trace generation.
    """
    import random

    # Persistent state for the diagnostic run
    diag_state = GLOBAL_CONTEXT.setdefault("vli_cache_diag", {"cache": {}, "history": []})
    cache = diag_state["cache"]
    traces = [f"### VLI Cache Heartbeat (Tick {iteration}/5)"]

    # 1. Decay Phase (Execute every tick)
    evicted = []
    for sym, data in list(cache.items()):
        data["heat"] -= 1
        if data["heat"] <= 0:
            evicted.append(sym)
            del cache[sym]
        else:
            traces.append(f"[CACHE_TRACE] Symbol {sym} heat decremented to {data['heat']} via decay.")

    for sym in evicted:
        traces.append(f"[CACHE_TRACE] Symbol {sym} evicted from cache due to TTL decay (Heat reached 0).")

    # 2. Arrival Phase (One new random symbol per tick)
    # 50 mocked 3-letter symbols (Simple subset: AAA-ZZZ)
    ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    new_sym = "".join(random.choices(ALPHABET, k=3))

    traces.append(f"[CACHE_TRACE] New symbol presentation: {new_sym} entering VLI pipeline.")

    if new_sym in cache:
        cache[new_sym]["heat"] += 1
        traces.append(f"[CACHE_TRACE] Symbol {new_sym} updated in contextual cache (Heat: {cache[new_sym]['heat']}).")
    else:
        cache[new_sym] = {"price": f"{random.uniform(50, 500):.2f}", "volume": f"{random.randint(1000, 100000)}", "heat": 1}
        traces.append(f"[CACHE_TRACE] Symbol {new_sym} added to contextual cache (Heat: 1).")

    # 3. Visualization Phase (Generate Dynamic Table JSON)
    rows = []
    for sym, data in cache.items():
        rows.append([sym, data["price"], data["volume"], {"type": "indicator", "value": data["heat"]}])

    table_json = {"type": "table", "id": f"vli_diag_tick_{iteration}", "headers": ["SYMBOL", "PRICE", "VOLUME", "HEAT"], "rows": rows}

    import json

    report = "\n".join([str(t) for t in traces]) + "\n\n```json\n" + json.dumps(table_json) + "\n```"
    return report


@tool
async def clear_vli_diagnostic() -> str:
    """
    VLI System Administrative Tool: Resets the autonomic cache simulation.
    Clears all persistent symbols, heat data, and trace history.
    """
    GLOBAL_CONTEXT["vli_cache_diag"] = {"cache": {}, "history": []}
    logger.info("[VLI_ADMIN] Cache simulation state has been reset.")
    return "VLI Cache Simulation state has been successfully cleared. Ready for fresh diagnostic run."


@tool
async def get_stock_quote(ticker: str, period: str = "1d", interval: str = "1m", use_fast_path: bool = True, use_finviz_fallback: bool = False, force_refresh: bool = False) -> dict[str, Any] | str:
    """Retrieve realtime or delayed stock quote for a specific ticker symbol. Fast-fetch skips full history parsing where possible.
    If 'use_finviz_fallback' is True, it strictly bypasses Yahoo Finance and fetches directly via the Finviz scraper module.
    If 'force_refresh' is True, it invalidates any existing cache for this symbol before fetching."""

    DatastoreManager.ensure_worker_started()
    norm_ticker = _normalize_ticker(ticker)

    # [HARDENING] Prevent LLM hallucination of 'NEWS' as a ticker
    if norm_ticker == "NEWS":
        return "Action Denied: 'NEWS' is not a valid stock symbol. Please infer the actual target asset from the context and try again, or use the search tool if you need to fetch news."


    logger.info(f"[DIAGNOSTIC] get_stock_quote called for {ticker} | force_refresh={force_refresh} | use_fast_path={use_fast_path}")

    if force_refresh:
        logger.info(f"VLI_SYSTEM: Force refresh requested for {ticker}. Invalidating cache.")
        DatastoreManager.invalidate_cache(norm_ticker)

    if use_finviz_fallback:
        logger.info(f"VLI_SYSTEM: User explicitly requested Finviz fallback for {ticker}.")
        try:
            fin_quotes = await fetch_finviz_quotes([norm_ticker])
            if norm_ticker.upper() in [k.upper() for k in fin_quotes.keys()]:
                quote = fin_quotes[norm_ticker.upper()]
                return {"symbol": norm_ticker, "price": quote["price"], "volume": quote["volume"], "source": f"Finviz {quote['source']} (Explicit Override)", "note": "[VLI_SYSTEM] Successfully extracted via Finviz scraper as requested."}
        except Exception as e:
            logger.error(f"Explicit Finviz fallback failed: {e}")
            return f"[ERROR]: Requested Finviz fallback failed to extract data: {e}"

    try:
        # 1. Warm Cache Phase: Check global scope for recent data (< 2 mins)
        # Refactor Phase 2: Use DatastoreManager.get_artifact
        entry = DatastoreManager.get_artifact(norm_ticker, "history", interval)
        if entry:
            # [STABILITY] Accept data up to 120s old for immediate resonance
            age_sec = (datetime.now() - entry["updated_at"]).total_seconds()
            if age_sec < 120:
                logger.info(f"VLI Fast-Path: Warm cache hit for {norm_ticker} (Age: {age_sec:.1f}s)")
                
                data_val = entry["data"]
                # If data is a dict (Phase 3 storage), extract the price
                if isinstance(data_val, dict):
                    price_val = data_val.get("raw", {}).get("Close")
                    if price_val:
                        return {"symbol": norm_ticker, "price": price_val, "change": 0.0, "is_cached": True}
                
                # Fallback to regex for string-based cache
                try:
                    price_val = float(re.search(r"Close\*\*: (\d+\.?\d*)", str(data_val)).group(1))
                    return {"symbol": norm_ticker, "price": price_val, "change": 0.0, "is_cached": True}
                except Exception:
                    pass  # Fall through to fetch if parse fails

        # 2. Fast-Fetch Phase: Bypassing the global throttle lock for single-ticker quotes
        # [REPLAY_INSTRUMENTATION] Bypass Fast-Path for Replay Mode to ensure temporal sync
        from src.utils.temporal import get_effective_now
        is_replay = abs((datetime.now() - get_effective_now()).total_seconds()) > 5

        # [NEW] Pre/Post Market Price Engine
        # If market is closed, fetch the active pre/post market price to override previous close values
        if not is_replay:
            try:
                import pytz
                est = pytz.timezone('America/New_York')
                now_est = datetime.now(est)
                is_closed = now_est.weekday() >= 5 or now_est.time() < __import__('datetime').time(9, 30) or now_est.time() >= __import__('datetime').time(16, 0)
                if is_closed:
                    logger.info(f"VLI Fast-Path: Market is closed. Fetching active pre/post market price for {norm_ticker}")
                    df = await asyncio.to_thread(
                        yfinance.download,
                        tickers=[norm_ticker],
                        period="1d",
                        interval="1m",
                        group_by="ticker",
                        session=_get_session(),
                        progress=False,
                        threads=False,
                        timeout=5.0,
                        auto_adjust=False,
                        prepost=True
                    )
                    if df is not None and not df.empty:
                        ticker_df = _extract_ticker_data(df, norm_ticker)
                        if not ticker_df.empty:
                            last_row = ticker_df.dropna(subset=["Close"]).iloc[-1]
                            price = float(last_row["Close"])
                            
                            # Fallback for previous close
                            try:
                                t_obj = await asyncio.wait_for(asyncio.to_thread(yfinance.Ticker, norm_ticker, session=_get_session()), timeout=3.0)
                                prev_close = float(t_obj.fast_info.previous_close)
                            except:
                                prev_close = price
                                
                            return {
                                "symbol": norm_ticker,
                                "price": price,
                                "change": ((price / prev_close) - 1) * 100 if prev_close else 0.0,
                                "volume": int(last_row["Volume"]),
                                "is_prepost_price": True,
                            }
            except Exception as e:
                logger.warning(f"VLI Fast-Path: Pre/Post market fetch failed for {norm_ticker}: {e}")
        
        if use_fast_path and not is_replay:
            logger.info(f"VLI Fast-Path: Starting lock-free fast-fetch for {norm_ticker}")
            try:
                # [STABILITY] 5s hard-timeout for all data retrieval threads
                t_obj = await asyncio.wait_for(asyncio.to_thread(yfinance.Ticker, norm_ticker, session=_get_session()), timeout=5.0)
                
                # [DEFENSIVE] fast_info can throw KeyError: 'currentTradingPeriod' for invalid/delisted tickers
                try:
                    fast = t_obj.fast_info
                    if fast is not None and hasattr(fast, "last_price") and fast.last_price:
                        return {
                            "symbol": norm_ticker,
                            "price": fast.last_price,
                            "change": ((fast.last_price / fast.previous_close) - 1) * 100 if hasattr(fast, "previous_close") and fast.previous_close else 0.0,
                            "volume": getattr(fast, "last_volume", 0),
                            "is_fast_fetch": True,
                        }
                except (KeyError, AttributeError, Exception) as e:
                    logger.warning(f"VLI: fast_info access failed for {norm_ticker}: {e}")
                    # Fall through to batched history
                
                logger.info(f"VLI: Fast-info empty or failed for {norm_ticker}, falling back to batched history.")
            except Exception as fe:
                logger.warning(f"VLI: Fast-fetch thread failed for {norm_ticker}, falling back to batched fetch: {fe}")

        # 3. Standard Batched Fetch (Tier 3 fallback)
        # [REPLAY_INSTRUMENTATION] Expand window to 10d for Replay to survive weekends
        period = "10d" if is_replay else period
        data = await asyncio.wait_for(asyncio.to_thread(_fetch_batch_history, [norm_ticker], period, interval), timeout=5.0)

        # Extract using normalized ticker to ensure level-0 match
        ticker_df = _extract_ticker_data(data, norm_ticker)

        if ticker_df.empty:
            return f"[ERROR]: No data found for ticker '{ticker}' (normalized: {norm_ticker})."

        # [STABILITY] Filter out "Ghost Rows" (partial NaNs at Market Close)
        # We need at least 'Close' and 'Volume' or 'Open' to consider a row valid
        stable_df = ticker_df.dropna(subset=[col for col in ticker_df.columns if col.lower() in ["close", "adj close", "volume", "open"]], how="all")
        if stable_df.empty:
            return f"[ERROR]: No stable data points found for '{ticker}'."
            
        last_row = stable_df.iloc[-1]

        # Case-Insensitive Column Resolution
        def _get_val(row, keys):
            for k in keys:
                if k in row.index: return float(row[k])
                if k.lower() in row.index: return float(row[k.lower()])
                if k.capitalize() in row.index: return float(row[k.capitalize()])
            return None

        quote_price = _get_val(last_row, ["Close", "Adj Close"])
        if quote_price is None:
            return f"[ERROR]: Could not find price column for '{ticker}'. Columns: {list(last_row.index)}"

        prev_close = _get_val(last_row, ["Open"]) # Fallback for change calc if only 1 day
        if len(stable_df) > 1:
            prev_close = _get_val(stable_df.iloc[-2], ["Close", "Adj Close"])

        return {
            "symbol": norm_ticker,
            "original_ticker": ticker.upper(),
            "price": quote_price,
            "high": float(last_row["High"]),
            "low": float(last_row["Low"]),
            "volume": int(last_row["Volume"]),
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except TimeoutError:
        logger.error(f"Timeout fetching quote for {ticker}")
        return "[ERROR]: Data retrieval timed out (15s)."
    except Exception as e:
        logger.error(f"Error fetching quote for {ticker}: {e}")

        # [NEW] Snapper Data Fallback (Finviz)
        logger.info(f"VLI_SYSTEM: YFinance failed for {ticker}. Deploying Snapper Data Fallback (Finviz)...")
        try:
            # Try to get structured data from Finviz first
            fin_quotes = await fetch_finviz_quotes([norm_ticker])
            if norm_ticker.upper() in [k.upper() for k in fin_quotes.keys()]:
                quote = fin_quotes[norm_ticker.upper()]
                return {
                    "symbol": norm_ticker,
                    "price": quote["price"],
                    "volume": quote["volume"],
                    "source": f"Finviz {quote['source']} (Fallback)",
                    "note": f"[VLI_SYSTEM] YFinance failed ({str(e)}). Sucessfully extracted via Finviz scraper.",
                }

            # If data extraction fails, fall back to the absolute last resort: Visual Snapshot
            logger.info(f"VLI_SYSTEM: Finviz extraction failed for {ticker}. Falling back to Visual TradingView Snapshot.")
            # Format the TradingView chart URL (Symbol must be correct for TV)
            # Remove prefixes/suffixes for clean TV lookup
            tv_symbol = norm_ticker.replace("^", "").split(".")[0]
            tv_url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}"

            # Use the tool to get the snapshot - reaching for coroutine safely
            tool_fn = getattr(snapper, "coroutine", getattr(snapper, "func", None))
            if tool_fn:
                snap_json = await tool_fn(url=tv_url)
            else:
                snap_json = await snapper.invoke({"url": tv_url})

            import json

            snap_res = json.loads(snap_json)

            if isinstance(snap_res, dict) and "images" in snap_res:
                return {
                    "symbol": norm_ticker,
                    "price": "SEE_IMAGE",
                    "source": "Visual TradingView Snapshot (Fallback)",
                    "note": f"[VLI_SYSTEM] Data retrieval failed ({str(e)}). Headless chart captured for visual analysis.",
                    "images": snap_res["images"],
                }
            else:
                err_msg = snap_res.get("error", "Unknown Error") if isinstance(snap_res, dict) else str(snap_res)
                return f"[ERROR]: Primary fetch failed ({str(e)}) AND Visual Fallback returned invalid data: {err_msg}"
        except Exception as fe:
            import traceback

            tb = traceback.format_exc()
            logger.error(f"Fallback also failed: {fe}\n{tb}")
            return f"[ERROR]: Primary fetch failed ({str(e)}) and Visual Fallback failed ({str(fe)}). Check system logs for traceback."


@tool
async def get_sharpe_ratio(ticker: str) -> str:
    """
    Technical Analysis: Calculate the Sharpe Ratio for a given ticker based on last 252 trading days.
    """
    try:
        df = await asyncio.to_thread(_fetch_stock_history, ticker, "1y", "1d")
        if df.empty:
            return f"[ERROR]: No data for {ticker}"

        returns = df["Close"].pct_change().dropna()
        if len(returns) < 50:
            return "Insufficient data for Sharpe calculation."

        sharpe = (returns.mean() / returns.std()) * (252**0.5)
        return f"Sharpe Ratio ({ticker}): {sharpe:.2f}"
    except Exception as e:
        return f"[ERROR]: {str(e)}"


@tool
async def get_sortino_ratio(ticker: str) -> str:
    """
    Technical Analysis: Calculate the Sortino Ratio (downside risk-adjusted) for a given ticker.
    """
    try:
        from src.tools.scanner import batch_fetch_sortino
        # Call the scanner's Sortino batcher to ensure exact pipeline parity
        sortino_map = await batch_fetch_sortino([ticker])
        if not sortino_map or ticker not in sortino_map:
            return f"[ERROR]: No data for {ticker}"
            
        sortino = sortino_map[ticker]
        if sortino == 0.0:
            return f"Sortino Ratio ({ticker}): 0.0 (Or N/A due to lack of downside volatility)"
            
        return f"Sortino Ratio ({ticker}): {sortino:.2f}"
    except Exception as e:
        return f"[ERROR]: {str(e)}"


def _calculate_sortino_ratio(ticker_df: pd.DataFrame, risk_free_rate: float = 0.0) -> float:
    """
    Calculates the annualized Sortino Ratio for a given ticker DataFrame.
    Sortino = (R_p - R_f) / DownsideDev
    """
    try:
        # Use 'Close' or 'adj close' for returns
        col = "Close" if "Close" in ticker_df.columns else "close"
        if col not in ticker_df.columns: return 0.0
        
        returns = ticker_df[col].pct_change().dropna()
        if returns.empty: return 0.0
        
        # Annualization factor (Daily to Annual)
        # Assuming Daily data (1d)
        mean_return = returns.mean() * 252
        
        # Downside Deviation: Std Dev of negative returns only
        downside_returns = returns[returns < risk_free_rate]
        if downside_returns.empty: return 0.0 # No downside risk detected? 
        
        # Note: We calculate variance using N (len(returns)) not len(downside_returns) 
        # for a standard Sortino calculation.
        downside_dev = np.sqrt((downside_returns**2).sum() / len(returns)) * np.sqrt(252)
        
        if downside_dev == 0: return 0.0
        
        return (mean_return - risk_free_rate) / downside_dev
    except Exception as e:
        logger.error(f"VLI_ECON: Sortino calculation failed: {e}")
        return 0.0

@tool
async def get_macro_symbols(fast_update: bool = False) -> str:
    """
    Institutional Macro Registry Tool: Fetches the current states of all registered macro indicators
    (Indices, Yields, Commodities, Crypto). 
    
    If fast_update=True: Returns only Price, Vol, Change (15s heartbeat).
    If fast_update=False: Returns full analysis including Sortino Ratio and Level Analysis (5m cycle).
    """
    from src.services.macro_registry import macro_registry
    from datetime import datetime
    import json
    import os

    macros = macro_registry.get_macros()
    results = {}
    rows = []
    candidates = []
    
    existing_rows = {}
    existing_candidates = {}
    try:
        from src.config.vli import get_vli_path
        transit_path = get_vli_path(os.path.join("01_Transit", "Buckets", "MACRO_WATCHLIST_state.json"))
        if os.path.exists(transit_path):
            with open(transit_path, encoding="utf-8") as f:
                old_state = json.load(f)
                for r in old_state.get("rows", []):
                    if len(r) > 1:
                        existing_rows[r[1].upper()] = r
                for c in old_state.get("candidates", []):
                    if c.get("symbol"):
                        existing_candidates[c["symbol"].upper()] = c
    except Exception as ex_err:
        logger.warning(f"VLI: Failed to load previous macro state for fallback: {ex_err}")

    # Batch fetch using the datastore infrastructure
    ticker_list = list(macros.values())
    logger.info(f"VLI_SYSTEM: Fetching batch macro data for: {ticker_list}")
    try:
        # [REPLAY_INSTRUMENTATION] Replay-Aware Sparkline Fetch
        ref_time = get_effective_now()
        
        # [MARKET_ANCHOR] Removed so futures reflect real-time trailing 100 minutes.
        logger.info(f"VLI_SYSTEM: Using direct trailing time for Sparkline target: {ref_time}")
        
        is_replay = abs((datetime.now() - ref_time).total_seconds()) > 5

        # [SPARKLINE_INTERVAL_LOCK] Fetch 1m data directly, bypassing Replay delegate
        # yfinance is notoriously buggy with end=... for intraday 1m data, causing full-day omissions.
        async def _fetch_direct_sparkline():
            def _do_fetch():
                return yfinance.download(
                    ticker_list,
                    period="2d",
                    interval="1m",
                    progress=False,
                    threads=False,
                    timeout=15.0,
                    auto_adjust=False,
                    prepost=True
                )
            async with _get_yf_semaphore():
                res = await asyncio.to_thread(_do_fetch)
            if res is not None and not res.empty:
                # [TZ_ALIGNMENT] Force identical timezone across all tickers
                try:
                    res.index = pd.to_datetime(res.index, utc=True).tz_convert('America/New_York').tz_localize(None)
                except Exception:
                    res.index = pd.to_datetime(res.index).tz_localize(None)
                return res
            return pd.DataFrame()
            
        # High-Fidelity Data Retrieval (2-Day 1M window for sub-second anchoring)
        tasks = [
            asyncio.to_thread(_fetch_batch_history, ticker_list, "5d", "1d"),
            _fetch_direct_sparkline()
        ]
        if not fast_update:
            tasks.append(asyncio.to_thread(_fetch_batch_history, ticker_list, "1y", "1d"))
            
        results_raw = await asyncio.wait_for(asyncio.gather(*tasks), timeout=25.0)
        data_1d = results_raw[0]
        data_5m = results_raw[1]
        data_1y = results_raw[2] if len(results_raw) > 2 else None
        
        # [MEMORY_ANCHOR] Precise Slice for Sparkline Temporal Alignment
        try:
            if not data_5m.empty:
                safe_index = data_5m.index
                if getattr(safe_index, 'tz', None) is not None:
                     safe_index = safe_index.tz_convert('America/New_York').tz_localize(None)
                data_5m = data_5m[safe_index <= pd.Timestamp(ref_time).tz_localize(None)]
        except Exception as filter_err:
             logger.warning(f"VLI: In-memory anchor filter failed: {filter_err}")

        # [INSTITUTIONAL SORTINO] Extract dynamic annual risk-free rate from ^TNX
        dynamic_rf = 0.0428
        if data_1y is not None:
            tnx_df = _extract_ticker_data(data_1y, "^TNX")
            if not tnx_df.empty:
                c_col = "Close" if "Close" in tnx_df.columns else "close"
                if c_col in tnx_df.columns:
                    try:
                        latest_tnx = float(tnx_df[c_col].dropna().iloc[-1])
                        dynamic_rf = latest_tnx / 100.0
                    except:
                        pass

        from src.tools.scanner import calculate_sortino_ratio

        for label, ticker in macros.items():
            ticker_df = _extract_ticker_data(data_1d, ticker)
            
            # Fallback: If batch fetch failed for this specific ticker, try individual fetch
            if ticker_df.empty:
                logger.info(f"VLI: Batch fetch missing {ticker}, falling back to individual yfinance lookup.")
                try:
                    ticker_df = await asyncio.to_thread(_fetch_batch_history, [ticker], "5d", "1d", True)
                    ticker_df = _extract_ticker_data(ticker_df, ticker)
                except Exception as fe:
                    logger.error(f"VLI: Fallback fetch failed for {ticker}: {fe}")

            if ticker_df.empty:
                results[label] = {"symbol": ticker, "status": "Error (No Data)"}
                if ticker.endswith('=F'):
                    display_ticker = '/' + ticker.replace('=F', '')
                elif ticker.endswith('.CMX') or label.upper() in ["MGC", "MGCZ2026", "ES", "MES", "NQ", "MNQ", "YM", "MYM", "RTY", "M2K", "CL", "MCL", "GC", "NKD", "MNK"]:
                    clean_l = label.replace('/', '').replace('=F', '')
                    display_ticker = '/' + clean_l
                else:
                    display_ticker = ticker
                display_ticker_upper = display_ticker.upper()
                if display_ticker_upper in existing_rows and display_ticker_upper in existing_candidates:
                    rows.append(existing_rows[display_ticker_upper])
                    candidates.append(existing_candidates[display_ticker_upper])
                    logger.info(f"VLI: Fetch failed for {ticker}. Reusing last known macro state data.")
                else:
                    is_yield = any(y in ticker.upper() for y in ["TNX", "TYX", "FVX", "BX", "IRX"])
                    price_display = "0.00%" if is_yield else "$0.00"
                    from src.tools.macros import MACRO_NAMES
                    display_name = MACRO_NAMES.get(label, label)
                    if display_name == label and label.upper() == "CL":
                        display_name = "WTI Crude Oil"
                    rows.append([
                        display_name,
                        display_ticker,
                        price_display,
                        {"value": 0.0, "type": "text"},
                        0.0,
                        {"type": "sparkline", "value": [{"v": 0.0, "is_prev": False}] * 32}
                    ])
                    candidates.append({
                        "symbol": display_ticker,
                        "name": display_name,
                        "price": 0.0,
                        "change": 0.0,
                        "sortino": 0.0,
                        "grade": "F",
                        "heat_score": 0,
                        "tier": "Macro"
                    })
                continue

            last_row = ticker_df.iloc[-1]
            prev_row = ticker_df.iloc[-2] if len(ticker_df) > 1 else last_row
            
            try:
                # Handle pandas Series duplication gracefully
                p_c = last_row["Close"] if "Close" in last_row else last_row["close"]
                price = float(p_c.iloc[0]) if isinstance(p_c, pd.Series) else float(p_c)
                
                p_p = prev_row["Close"] if "Close" in prev_row else prev_row["close"]
                prev_price = float(p_p.iloc[0]) if isinstance(p_p, pd.Series) else float(p_p)
                
                change = ((price / prev_price) - 1) * 100
            except Exception as pe:
                logger.error(f"VLI: Price parse failed: {pe}")
                price = 0.0
                change = 0.0

            # [SPARKLINE_EXTRACTION] High-Fidelity 1M Scaling (390m trading session)
            sparkline_df = _extract_ticker_data(data_5m, ticker)
            
            # Fallback for individual missing 1m data due to batch merging quirks (futures vs crypto)
            if sparkline_df.empty or sparkline_df.isna().all().all():
                try:
                    logger.info(f"VLI: Batch 1m empty for {ticker}, fetching individually.")
                    sdf = await asyncio.to_thread(yfinance.download, ticker, period="5d", interval="1m", prepost=True, progress=False, threads=False)
                    if sdf is not None and not sdf.empty:
                        try:
                            sdf.index = pd.to_datetime(sdf.index, utc=True).tz_convert('America/New_York').tz_localize(None)
                        except Exception:
                            sdf.index = pd.to_datetime(sdf.index).tz_localize(None)
                        sparkline_df = sdf
                except Exception as ef:
                    logger.warning(f"VLI: Fallback 1m fetch failed for {ticker}: {ef}")

            sparkline_values = _bucket_sparkline_data(sparkline_df, ref_time, price, num_points=32, span_minutes=240, session_mode=True, step_minutes=5)

            # [RISK_METRICS] Institutional Sortino Ratio (1y)
            sortino = 0.0
            if data_1y is not None:
                ticker_1y = _extract_ticker_data(data_1y, ticker)
                if ticker_1y.empty:
                    logger.info(f"VLI: Sortino batch missing {ticker}, falling back to individual yfinance.")
                    try:
                        ticker_1y = await asyncio.to_thread(_fetch_batch_history, [ticker], "1y", "1d", force_yf=True)
                        ticker_1y = _extract_ticker_data(ticker_1y, ticker)
                    except Exception as fe:
                        logger.error(f"VLI: Sortino Fallback failed for {ticker}: {fe}")
                
                c_col = "Close" if "Close" in ticker_1y.columns else "close"
                if not ticker_1y.empty and c_col in ticker_1y.columns:
                    rets = ticker_1y[c_col].pct_change().dropna()
                    sortino = calculate_sortino_ratio(rets, annual_rf=dynamic_rf, interval="1d")

            results[label] = {
                "symbol": ticker,
                "price": round(price, 4),
                "change_pct": round(change, 2),
                "sortino": round(sortino, 2),
                "volume": int(last_row["Volume"].iloc[0]) if "Volume" in last_row and isinstance(last_row["Volume"], pd.Series) else (int(last_row["Volume"]) if "Volume" in last_row else 0),
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # [STRUCTURAL_JSON] Format for DynamicTable Component
            # Headers: ["Asset", "Ticker", "Price", "Change %", "Sortino", "Trend (5m)"]
            # [YIELD_FORMATTING] Yields must be in % not $
            is_yield = any(y in ticker.upper() for y in ["TNX", "TYX", "FVX", "BX", "IRX"])
            price_display = f"{price:.2f}%" if is_yield else f"${price:,.2f}"
            
            from src.tools.macros import MACRO_NAMES
            
            # Resolve descriptive name for UI
            display_name = MACRO_NAMES.get(label, label)
            if display_name == label and label.upper() == "CL":
                display_name = "WTI Crude Oil"

            if ticker.endswith('=F'):
                display_ticker = '/' + ticker.replace('=F', '')
            elif ticker.endswith('.CMX') or label.upper() in ["MGC", "MGCZ2026", "ES", "MES", "NQ", "MNQ", "YM", "MYM", "RTY", "M2K", "CL", "MCL", "GC", "NKD", "MNK"]:
                clean_l = label.replace('/', '').replace('=F', '')
                display_ticker = '/' + clean_l
            else:
                display_ticker = ticker

            rows.append([
                display_name,
                display_ticker,
                price_display,
                {"value": round(change, 2), "type": "text"},
                round(sortino, 2),
                {"type": "sparkline", "value": sparkline_values}
            ])

            if sortino >= 5.0: letter_grade = "S"
            elif sortino >= 2.5: letter_grade = "A"
            elif sortino >= 2.0: letter_grade = "B"
            elif sortino >= 1.0: letter_grade = "C"
            else: letter_grade = "F"
            
            base_score = 50.0
            if letter_grade == "A": base_score += 15.0
            elif letter_grade == "B": base_score += 5.0
            elif letter_grade == "C": base_score -= 10.0
            elif letter_grade == "F": base_score -= 25.0
            base_score += (sortino * 10.0)
            base_score += min(20.0, change * 0.8)
            heat_score = int(max(0, min(100, base_score)))
            
            candidates.append({
                "symbol": display_ticker,
                "name": display_name,
                "price": price,
                "change": change,
                "sortino": sortino,
                "grade": letter_grade,
                "heat_score": heat_score,
                "tier": "Macro"
            })

        # Create Structural Response Object
        response_obj = {
            "type": "table",
            "headers": ["Asset", "Ticker", "Price", "Change %", "Sortino", "Trend (5m)"],
            "rows": rows,
            "candidates": candidates,
            "metadata": {
                "origin": str(ref_time),
                "is_replay": is_replay,
                "is_fast_pulsar": fast_update,
                "source": "VLI_DATA_ENGINE_V2"
            }
        }

        # Create Artifact for persistence
        artifact_path = os.path.join("data", "artifacts", "get_macro_symbols.json")
        os.makedirs(os.path.dirname(artifact_path), exist_ok=True)
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(response_obj, f, indent=4)

        # [NEW] Synchronize to VLI Transit Bucket (Dashboard Feed)
        from src.config.vli import get_vli_path
        transit_path = get_vli_path(os.path.join("01_Transit", "Buckets", "MACRO_WATCHLIST_state.json"))
        try:
            os.makedirs(os.path.dirname(transit_path), exist_ok=True)
            with open(transit_path, "w", encoding="utf-8") as f:
                json.dump(response_obj, f, indent=4)
            logger.info(f"VLI_SYSTEM: Macro state synchronized to transit bucket: {transit_path}")
        except Exception as te:
            logger.error(f"VLI_SYSTEM: Failed to sync macro state: {te}")

        return json.dumps(response_obj)

    except Exception as e:
        import traceback
        try:
            with open("macro_debug_error.txt", "w", encoding="utf-8") as df:
                df.write(f"VLI_SYSTEM: Exception in get_macro_symbols: {e}\n{traceback.format_exc()}")
        except Exception:
            pass
        return json.dumps({"error": str(e)})
        return f"[ERROR]: Failed to fetch macro indicators: {str(e)}"


@tool
async def get_macro_regime(ticker: str) -> str:
    """
    Evaluates the basic macro regime for a given ticker or index.
    Currently specifically tuned for $VIX monitoring.
    """
    try:
        norm_ticker = _normalize_ticker(ticker)
        # Use fast fetch for quotes
        data = await get_stock_quote.ainvoke({"ticker": norm_ticker, "use_fast_path": True, "force_refresh": False})
        if isinstance(data, dict) and "price" in data:
            price = data["price"]
            # Visual fallback could result in 'SEE_IMAGE'
            if isinstance(price, (int, float)):
                if norm_ticker == "^VIX":
                    if price > 20.0:
                        return "STRESS"
                    elif price < 15.0:
                        return "COMPLACENT"
                    else:
                        return "NORMAL"
                
                # Generalized naive fallback
                change = data.get("change", 0)
                if isinstance(change, (int, float)):
                    if change > 1.0:
                        return "BULLISH"
                    elif change < -1.0:
                        return "BEARISH"
                return "NEUTRAL"
        return "UNKNOWN"
    except Exception as e:
        logger.error(f"Regime Tool Error: {e}")
        return f"[ERROR]: {str(e)}"


@tool
async def get_sparkline_audit_vli(ticker: str, ref_time_ms: int = None) -> str:
    """
    High-Fidelity Audit Engine: Returns 30 strictly sampled ground-truth quotes.
    Phase-locks to ref_time_ms if provided to ensure dashboard alignment.
    """
    import json
    from datetime import datetime, timedelta
    import pandas as pd
    from src.utils.temporal import get_effective_now
    
    norm_ticker = _normalize_ticker(ticker)
    
    # [PHASE_LOCK] Synchronize with the dashboard's last refresh point
    if ref_time_ms:
        ref_time = datetime.fromtimestamp(ref_time_ms / 1000.0)
    else:
        ref_time = get_effective_now()
    
    try:
        # Fetch 1m data for high-precision 10m sampling
        data = await asyncio.wait_for(asyncio.to_thread(_fetch_batch_history, [norm_ticker], "5d", "1m"), timeout=15.0)
        df = _extract_ticker_data(data, norm_ticker)
        
        if df.empty:
            return json.dumps({"error": f"No ground truth for {ticker}"})
            
        current_price = float(df.iloc[-1]["Close"] if "Close" in df.columns else df.iloc[-1]["close"])
        # Audit sync: 20 points over 390m trading session
        audit_values = _bucket_sparkline_data(df, ref_time, current_price, num_points=20, span_minutes=100)
        
        interval = 390.0 / 19.0
        audit_results = []
        for i, val in enumerate(audit_values):
            target_time = ref_time - timedelta(minutes=(19-i)*interval)
            audit_results.append({
                "time": target_time.strftime("%m-%d %H:%M"),
                "price": val
            })

        return json.dumps({
            "ticker": ticker,
            "ref_time": ref_time.isoformat(),
            "points": audit_results
        })
                
        return json.dumps({
            "ticker": norm_ticker,
            "anchor_time": ref_time.strftime("%Y-%m-%d %H:%M:%S"),
            "points": audit_results
        })
        
    except Exception as e:
        logger.error(f"Audit Tool Error: {e}")
        return json.dumps({"error": str(e)})

@tool
async def manage_macro_watchlist(action: str, label: str = None, ticker: str = None) -> str:
    """
    Administrative Watchlist Manager: Allows for dynamic and persistent modification 
    of the Macro Registry.
    
    Actions:
    - 'add': Requires both label and ticker. (e.g., 'Gold', 'GC=F')
    - 'remove': Requires label.
    - 'reset': Wipes all customizations and restores institutional factory defaults.
    """
    try:
        from src.services.macro_registry import macro_registry
        symbols = list(macro_registry.get_macros().values())
        logger.info(f"VLI_SYSTEM: Fetching batch macro data for: {symbols}")
        action = action.lower().strip()
        if action == "add":
            if not label or not ticker:
                return "[ERROR]: 'add' action requires both 'label' and 'ticker'."
            macro_registry.update_macro(label, ticker)
            return f"SUCCESS: Added '{label}' ({ticker}) to the persistent macro watchlist."
            
        elif action == "remove":
            if not label:
                return "[ERROR]: 'remove' action requires a 'label'."
            macro_registry.remove_macro(label)
            return f"SUCCESS: Removed '{label}' from the macro watchlist."
            
        elif action == "reset":
            macro_registry.reset_to_defaults()
            return "SUCCESS: Macro Watchlist has been factory reset to institutional defaults."
            
        else:
            return f"[ERROR]: Unsupported action '{action}'. Use 'add', 'remove', or 'reset'."
            
    except Exception as e:
        logger.error(f"Watchlist Manager Error: {e}")
        return f"[ERROR]: Failed to manage watchlist: {str(e)}"
