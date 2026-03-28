# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Agent: Scout - Core financial primitives and data retrieval.
# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
import asyncio
import yfinance as yf
import pandas as pd
import threading
import time
from langchain_core.tools import tool
from typing import Dict, Any, Union, List, Optional

# Use curl_cffi for industrial-strength browser spoofing
from curl_cffi.requests import Session

logger = logging.getLogger(__name__)

from .shared_storage import SCOUT_CONTEXT, GLOBAL_CONTEXT

# 1. Private context
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context
_SHARED_RESOURCE_CONTEXT = SCOUT_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

# 4. Specialized Analysis Cache (Isolated from Scout)
_ANALYSIS_CACHE: Dict[str, Any] = {}

# Global lock to prevent slamming Yahoo Finance API
_YF_THROTTLE_LOCK = threading.Lock()

# Thread-local storage for sessions to avoid pickling/multiprocessing issues
_thread_local = threading.local()

def _get_session():
    """Retrieve or create a thread-local curl_cffi session."""
    if not hasattr(_thread_local, "session"):
        logger.info("Initializing new curl_cffi session for current thread...")
        _thread_local.session = Session(impersonate="chrome120")
        _thread_local.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://finance.yahoo.com/'
        })
    return _thread_local.session

_eager_worker_task = None
def _ensure_worker_started():
    global _eager_worker_task
    if _eager_worker_task is None:
        try:
            loop = asyncio.get_running_loop()
            _eager_worker_task = loop.create_task(_eager_cache_worker())
            logger.info("Eager Cache Background Worker started.")
        except RuntimeError:
            pass

async def _eager_cache_worker():
    from src.config.loader import get_int_env
    from datetime import datetime, timedelta
    
    while True:
        try:
            await asyncio.sleep(60)
            
            expiry_minutes = get_int_env("CACHE_EXPIRY_MINUTES", 15)
            eager_limit = get_int_env("EAGER_CACHE_LIMIT", 5)
            
            ticker_metadata = _GLOBAL_RESOURCE_CONTEXT.get("ticker_metadata", {})
            history_cache = _GLOBAL_RESOURCE_CONTEXT.get("history_cache", {})
            
            if not ticker_metadata:
                continue
                
            sorted_by_heat = sorted(ticker_metadata.keys(), key=lambda sym: ticker_metadata[sym].get('heat', 0), reverse=True)
            top_eager = sorted_by_heat[:eager_limit]
            
            now = datetime.now()
            refresh_threshold = timedelta(minutes=expiry_minutes * 0.8) # Refresh at 80% to TTL
            
            for sym in top_eager:
                # Bypass mock data in background worker
                if sym.startswith(("HIGH_", "MOD_", "INACT_")):
                    continue
                    
                for cache_key, entry in list(history_cache.items()):
                    if cache_key.startswith(f"{sym}_"):
                        last_up = entry.get("last_updated")
                        if last_up and (now - last_up) >= refresh_threshold:
                            logger.info(f"[CACHE_SYNC] Eager background refresh triggered for hot ticker {sym}")
                            p = entry["period"]
                            i = entry["interval"]
                            try:
                                full_df = await asyncio.to_thread(_fetch_batch_history, [sym], p, i)
                                ticker_df = full_df.dropna()
                                if not ticker_df.empty:
                                    last_row = ticker_df.iloc[-1]
                                    data_str = f"### {sym}\n- **Period**: {p} | **Interval**: {i}\n- **Close**: {float(last_row['Close']):.2f}\n- **High**: {float(last_row['High']):.2f}\n- **Low**: {float(last_row['Low']):.2f}\n- **Volume**: {int(last_row['Volume']):,}\n"
                                    
                                    entry["data"] = data_str
                                    entry["last_updated"] = datetime.now()
                            except Exception as e:
                                logger.error(f"[CACHE_SYNC] Eager fetch failed for {sym}: {e}")
                                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Eager worker error: {e}")

def _fetch_batch_history(tickers: List[str], period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """
    Centralized batched fetcher for Yahoo Finance data.
    Ensures all requests are batched where possible and respects a 1-second throttle.
    """
    with _YF_THROTTLE_LOCK:
        logger.info(f"Executing batched fetch for {tickers} (p={period}, i={interval})")
        # Ensure tickers is a list for yf.download consistency
        if isinstance(tickers, str):
            tickers = [tickers]
            
        session = _get_session()
        
        logger.debug(f"[WEB REQUEST] Yahoo Finance fetching {len(tickers)} tickers: {tickers}")
        start_time = time.time()
        try:
            data = yf.download(
                tickers=tickers,
                period=period,
                interval=interval,
                group_by='ticker',
                session=session,
                progress=False,
                threads=False # Maintain throttle integrity
            )
            duration_ms = (time.time() - start_time) * 1000
            
            if data is not None and not data.empty:
                logger.debug(f"[WEB RESPONSE] Yahoo Finance fetch successful in {duration_ms:.2f}ms for {tickers}")
            else:
                logger.warning(f"[WEB RESPONSE] Yahoo Finance returned empty data in {duration_ms:.2f}ms for {tickers}")
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[ERROR] Yahoo Finance fetch failed after {duration_ms:.2f}ms for {tickers}: {e}", exc_info=True)
            raise
        
        # Hard delay to prevent rate limiting
        time.sleep(1.0)
        return data

def _extract_ticker_data(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Helper to extract a single ticker's dataframe from a multi-index yf.download result."""
    ticker_upper = ticker.upper()
    if isinstance(df.columns, pd.MultiIndex):
        # Handle case where level 0 is the ticker name
        if ticker_upper in df.columns.levels[0]:
            return df[ticker_upper].dropna(how='all')
        # If not in levels, try direct index access
        try: return df[ticker_upper].dropna(how='all')
        except: pass

    return df.dropna(how='all')
def _fetch_stock_history(ticker: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """
    Standard single-ticker fetcher. Automatically flattens MultiIndex for the requested ticker.
    Used by all analysis nodes (Analyst, SMC, EMA, etc.).
    """
    data = _fetch_batch_history([ticker], period, interval)
    return _extract_ticker_data(data, ticker)

@tool
async def get_symbol_history_data(symbols: List[str], period: str = "1d", interval: str = "1h", verbosity: int = 1, is_test_mode: bool = False) -> str:
    """
    Scout Primitive: Retrieve stock history for multiple symbols in a single batched request.
    Verbosity levels: 1 (Report only), 2 (Include fetch traces).
    """
    from datetime import datetime, timedelta
    from src.config.loader import get_int_env

    expiry_minutes = get_int_env("CACHE_EXPIRY_MINUTES", 15)
    _ensure_worker_started()

    logger.info(f"Scout fetching history for {symbols}")
    
    # Scout isolated
    history_cache = _GLOBAL_RESOURCE_CONTEXT.setdefault("history_cache", {})
    # Tracker removed
    
    now = datetime.now()
    results = []
    missing_symbols = []
    symbols_upper = [s.upper() for s in symbols]
    
    for sym in symbols:
        sym = sym.upper()
        # No heat tracking for Scout
        
        cache_key = f"{sym}_{period}_{interval}"
        cached_entry = history_cache.get(cache_key)
        
        is_stale = True
        if cached_entry and "last_updated" in cached_entry:
            age = (now - cached_entry["last_updated"]).total_seconds() / 60.0
            if age <= expiry_minutes:
                is_stale = False
                
        if not is_stale:
            logger.info(f"[CACHE_READ] Using warm lazy cache for {sym}")
            results.append(cached_entry["data"])
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
            # cached_tickers_set update removed
        
        # Handle generic MOCK_TICKER placeholder
        if "MOCK_TICKER" in symbols_upper:
            if verbosity >= 2:
                results.append("### MOCK_TICKER\n- [MOCK DATA]: Generic placeholder retrieved.")
            # cached_tickers_set update removed
            if "MOCK_TICKER" in others: others.remove("MOCK_TICKER")

        if others:
            try:
                full_df = await asyncio.to_thread(_fetch_batch_history, others, period, interval)
                for sym in others:
                    ticker_df = full_df.dropna() if len(others) == 1 else _extract_ticker_data(full_df, sym)
                    if ticker_df.empty:
                        results.append(f"### {sym}\n- [ERROR]: No data found.")
                        continue
                        
                    # Scout only writes to history_cache, never to the coordinate tracker
                    logger.info(f"[SCOUT_FETCH] Successfully retrieved {sym}.")
                    
                    last_row = ticker_df.iloc[-1]
                    data_str = f"### {sym}\n- **Period**: {period} | **Interval**: {interval}\n- **Close**: {float(last_row['Close']):.2f}\n- **High**: {float(last_row['High']):.2f}\n- **Low**: {float(last_row['Low']):.2f}\n- **Volume**: {int(last_row['Volume']):,}\n"
                    
                    history_cache[f"{sym}_{period}_{interval}"] = {
                        "data": data_str,
                        "last_updated": datetime.now(),
                        "period": period,
                        "interval": interval
                    }
                    results.append(data_str)
            except Exception as e:
                logger.error(f"Error: {e}")
                return f"[ERROR]: Failed to fetch history batch: {str(e)}"
            
    report = f"# Stock History Report\nGenerated at {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    report += "\n".join(results)
    return report.strip()


@tool
async def simulate_cache_volatility(num_high: int = 10, num_moderate: int = 30, num_inactive: int = 10) -> str:
    """
    Scout Primitive (Diagnostic): Artificially populates the global cache with mock tickers of varying usage 'heat' to test eager/lazy architecture.
    """
    from datetime import datetime, timedelta
    
    ticker_metadata = _GLOBAL_RESOURCE_CONTEXT.setdefault("ticker_metadata", {})
    history_cache = _GLOBAL_RESOURCE_CONTEXT.setdefault("history_cache", {})
    cached_tickers_set = _GLOBAL_RESOURCE_CONTEXT.setdefault("cached_tickers", set())
    
    now = datetime.now()
    stale_time = now - timedelta(seconds=10) # Immediately push past 5s boundary
    
    # 10 High Activity
    for i in range(num_high):
        sym = f"HIGH_{i}"
        ticker_metadata[sym] = {"heat": 100}
        history_cache[f"{sym}_1d_1h"] = {"data": f"### {sym}\nMock high heat", "last_updated": stale_time, "period": "1d", "interval": "1h"}
        cached_tickers_set.add(sym)
        
    # 30 Moderate Activity
    for i in range(num_moderate):
        sym = f"MOD_{i}"
        ticker_metadata[sym] = {"heat": 10}
        history_cache[f"{sym}_1d_1h"] = {"data": f"### {sym}\nMock mod heat", "last_updated": stale_time, "period": "1d", "interval": "1h"}
        cached_tickers_set.add(sym)
        
    # 10 Inactive
    for i in range(num_inactive):
        sym = f"INACT_{i}"
        ticker_metadata[sym] = {"heat": 1}
        history_cache[f"{sym}_1d_1h"] = {"data": f"### {sym}\nMock inactive", "last_updated": stale_time, "period": "1d", "interval": "1h"}
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
    return f"Successfully populated 50 mock stocks with distribution 10/30/10. Visual Heat Map is now available."

@tool
async def get_cache_heat_map() -> str:
    """
    System Admin Tool: Generates a high-fidelity visual representation of the current cache 'heat' distribution.
    Shows frequency counters using bar visualizations and color-coded health states.
    """
    ticker_metadata = _GLOBAL_RESOURCE_CONTEXT.get("ticker_metadata", {})
    if not ticker_metadata:
        return "Cache is currently empty."
        
    sorted_tickers = sorted(ticker_metadata.keys(), key=lambda s: ticker_metadata[s].get('heat', 0), reverse=True)
    
    lines = ["# VLI Hybrid Cache Heat Map", ""]
    lines.append("| Ticker | Heat Level | Activity Bar | Status |")
    lines.append("| :--- | :--- | :--- | :--- |")
    
    for sym in sorted_tickers:
        heat = ticker_metadata[sym].get('heat', 0)
        
        # Determine Color/Category
        if heat >= 25:
             status = "🟣 **Top 5**" if sorted_tickers.index(sym) < 5 else "🟢 **Top 10**"
             bar_char = "█"
        elif heat >= 8:
             status = "🟠 **Active**"
             bar_char = "▓"
        elif heat >= 4:
             status = "🟡 **Lazy**"
             bar_char = "▒"
        else:
             status = "🔴 **Evictable**"
             bar_char = "░"
             
        bar = bar_char * min(heat, 20) # Cap bar length for UI
        if heat > 20: bar += "+"
        
        lines.append(f"| {sym} | {heat} | `{bar}` | {status} |")
        
    return "\n".join(lines)


@tool
async def vli_cache_tick(iteration: int) -> str:
    """
    VLI System Diagnostic (Heartbeat): Executes a single iterative tick of the VLI autonomic cache simulation.
    Handles symbol arrival, heat decay, and trace generation.
    """
    import random
    from datetime import datetime
    
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
        cache[new_sym] = {
            "price": f"{random.uniform(50, 500):.2f}",
            "volume": f"{random.randint(1000, 100000)}",
            "heat": 1
        }
        traces.append(f"[CACHE_TRACE] Symbol {new_sym} added to contextual cache (Heat: 1).")
        
    # 3. Visualization Phase (Generate Dynamic Table JSON)
    rows = []
    for sym, data in cache.items():
        rows.append([
            sym, 
            data["price"], 
            data["volume"], 
            {"type": "indicator", "value": data["heat"]}
        ])
        
    table_json = {
        "type": "table",
        "id": f"vli_diag_tick_{iteration}",
        "headers": ["SYMBOL", "PRICE", "VOLUME", "HEAT"],
        "rows": rows
    }
    
    import json
    report = "\n".join(traces) + "\n\n```json\n" + json.dumps(table_json) + "\n```"
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
async def get_stock_quote(ticker: str, period: str = "5d", interval: str = "1d") -> Union[Dict[str, Any], str]:
    """
    Get current stock quote and OHLC data using the batched fetcher.
    """
    try:
        # Check for mock data (Diagnostic check)
        if ticker.upper().startswith(("HIGH_", "MOD_", "INACT_")) or ticker.upper() == "MOCK_TICKER":
             return {
                "symbol": ticker.upper(),
                "price": 100.0,
                "change": 0.0,
                "is_mock": True,
                "note": "Retrieved from diagnostic cache simulation."
            }

        data = await asyncio.to_thread(_fetch_batch_history, [ticker.upper()], period, interval)
        ticker_df = _extract_ticker_data(data, ticker.upper())
        
        if ticker_df.empty:
            return f"[ERROR]: No data found for ticker '{ticker}'."
        
        last_row = ticker_df.iloc[-1]
        
        # Ensure we have a valid price
        quote_price = float(last_row['Close'])
        
        return {
            "symbol": ticker.upper(),
            "price": quote_price,
            "high": float(last_row['High']),
            "low": float(last_row['Low']),
            "volume": int(last_row['Volume']),
            "last_updated": time.strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        logger.error(f"Error fetching quote for {ticker}: {e}")
        return f"[ERROR]: {str(e)}"

@tool
async def get_sharpe_ratio(ticker: str) -> str:
    """
    Technical Analysis: Calculate the Sharpe Ratio for a given ticker based on last 252 trading days.
    """
    try:
        df = await asyncio.to_thread(_fetch_stock_history, ticker, "1y", "1d")
        if df.empty: return f"[ERROR]: No data for {ticker}"
        
        returns = df['Close'].pct_change().dropna()
        if len(returns) < 50: return "Insufficient data for Sharpe calculation."
        
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
        df = await asyncio.to_thread(_fetch_stock_history, ticker, "1y", "1d")
        if df.empty: return f"[ERROR]: No data for {ticker}"
        
        returns = df['Close'].pct_change().dropna()
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) < 20: return "Insufficient downside data for Sortino calculation."
        
        sortino = (returns.mean() / downside_returns.std()) * (252**0.5)
        return f"Sortino Ratio ({ticker}): {sortino:.2f}"
    except Exception as e:
        return f"[ERROR]: {str(e)}"
