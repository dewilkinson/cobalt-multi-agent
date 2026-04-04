# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Agent: Scout - Core financial primitives and data retrieval.
# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import asyncio
import logging
import threading
import time
from typing import Any

import pandas as pd
import yfinance

# Use curl_cffi for industrial-strength browser spoofing
from curl_cffi.requests import Session
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

from src.tools.shared_storage import GLOBAL_CONTEXT, SCOUT_CONTEXT, history_cache

from .scraper import fetch_finviz_quotes
from .screenshot import snapper

# 1. Private context
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context
_SHARED_RESOURCE_CONTEXT = SCOUT_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

# 4. Specialized Analysis Cache (Isolated from Scout)
_ANALYSIS_CACHE: dict[str, Any] = {}

# Global semaphore to prevent slamming Yahoo Finance API
# We limit to 3 concurrent network requests to prevent rate limiting and head-of-line blocking.
_YF_SEMAPHORE: asyncio.Semaphore | None = None


def _get_yf_semaphore() -> asyncio.Semaphore:
    """Lazy initialization of the semaphore in the correct event loop."""
    global _YF_SEMAPHORE
    if _YF_SEMAPHORE is None:
        _YF_SEMAPHORE = asyncio.Semaphore(3)
    return _YF_SEMAPHORE


# Thread-local storage for sessions to avoid pickling/multiprocessing issues
_thread_local = threading.local()


def _get_session():
    """Retrieve or create a thread-local curl_cffi session."""
    if not hasattr(_thread_local, "session"):
        logger.info("Initializing new curl_cffi session for current thread...")
        _thread_local.session = Session(impersonate="chrome120")
        _thread_local.session.headers.update({"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://finance.yahoo.com/"})
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
    from datetime import datetime, timedelta

    from src.config.loader import get_int_env

    while True:
        try:
            await asyncio.sleep(60)

            expiry_minutes = get_int_env("CACHE_EXPIRY_MINUTES", 15)
            eager_limit = get_int_env("EAGER_CACHE_LIMIT", 5)

            ticker_metadata = _GLOBAL_RESOURCE_CONTEXT.get("ticker_metadata", {})
            history_cache = _GLOBAL_RESOURCE_CONTEXT.get("history_cache", {})

            if not ticker_metadata:
                continue

            sorted_by_heat = sorted(ticker_metadata.keys(), key=lambda sym: ticker_metadata[sym].get("heat", 0), reverse=True)
            top_eager = sorted_by_heat[:eager_limit]

            now = datetime.now()
            refresh_threshold = timedelta(minutes=expiry_minutes * 0.8)  # Refresh at 80% to TTL

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


def _normalize_ticker(ticker: str) -> str:
    """Consistently maps common tickers to their Yahoo Finance equivalents."""
    t = ticker.upper().strip()
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
    if t == "BTC" or t == "BTCUSDT":
        return "BTC-USD"
    if t == "ETH" or t == "ETHUSDT":
        return "ETH-USD"
    if t.endswith("USDT"):
        return t.replace("USDT", "-USD")
    if t == "GC" or t == "GOLD":
        return "GC=F"
    if t == "SI" or t == "SILVER":
        return "SI=F"
    if t == "EURUSD" or t == "EUR/USD":
        return "EURUSD=X"
    if t == "GBPUSD" or t == "GBP/USD":
        return "GBPUSD=X"

    # Handle S&P 100 / Common Discrepancies (Dots to Hyphens)
    # e.g., BRK.B -> BRK-B, BF.B -> BF-B
    # EXCLUSION: DX-Y.NYB requires the dot to be preserved
    if "." in t and t != "DX-Y.NYB":
        return t.replace(".", "-")

    return t


def _fetch_batch_history(tickers: list[str], period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """
    Centralized batched fetcher for Yahoo Finance data.
    Ensures all requests are batched where possible.
    Note: Throttling is now handled by the caller via the _YF_SEMAPHORE.
    """
    logger.info(f"Executing batched fetch for {tickers} (p={period}, i={interval})")
    mapped_tickers = [_normalize_ticker(t) for t in tickers]

    logger.debug(f"[WEB REQUEST] Yahoo Finance fetching {len(mapped_tickers)} tickers: {mapped_tickers}")
    start_time = time.time()
    try:
        data = yfinance.download(
            tickers=mapped_tickers,
            period=period,
            interval=interval,
            group_by="ticker",
            session=_get_session(),
            progress=False,
            threads=False,  # Maintain throttle integrity
        )
        duration_ms = (time.time() - start_time) * 1000

        if data is not None and not data.empty:
            logger.debug(f"[WEB RESPONSE] Yahoo Finance fetch successful in {duration_ms:.2f}ms for {mapped_tickers}")
        else:
            logger.warning(f"[WEB RESPONSE] Yahoo Finance returned empty data in {duration_ms:.2f}ms for {mapped_tickers}")
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[ERROR] Yahoo Finance fetch failed after {duration_ms:.2f}ms for {mapped_tickers}: {e}", exc_info=True)
        raise

    # Hard delay to prevent rate limiting
    time.sleep(1.0)
    return data


def _extract_ticker_data(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Helper to extract a single ticker's dataframe from a multi-index yf.download result.
    Will automatically try normalized ticker names if the original key is not present.
    """
    ticker_upper = ticker.upper()
    norm_ticker = _normalize_ticker(ticker)

    if isinstance(df.columns, pd.MultiIndex):
        # 1. Try original ticker
        if ticker_upper in df.columns.levels[0]:
            return df[ticker_upper].dropna(how="all")

        # 2. Try normalized ticker (VIX -> ^VIX)
        if norm_ticker in df.columns.levels[0]:
            return df[norm_ticker].dropna(how="all")

        # 3. Fallback to direct access if columns levels are flattened
        try:
            return df[ticker_upper].dropna(how="all")
        except:
            pass
        try:
            return df[norm_ticker].dropna(how="all")
        except:
            pass

    # Flat Index Case
    return df.dropna(how="all")


def _fetch_stock_history(ticker: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """
    Standard single-ticker fetcher. Automatically flattens MultiIndex for the requested ticker.
    Used by all analysis nodes (Analyst, SMC, EMA, etc.).
    """
    data = _fetch_batch_history([ticker], period, interval)
    return _extract_ticker_data(data, ticker)


@tool
async def get_symbol_history_data(symbols: list[str], period: str = "1d", interval: str = "1h", verbosity: int = 1, is_test_mode: bool = False) -> str:
    """
    Scout Primitive: Retrieve stock history for multiple symbols in a single batched request.
    Verbosity levels: 1 (Report only), 2 (Include fetch traces).
    """
    from datetime import datetime

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

        if others:
            try:
                # Use semaphore for throttling
                async with _get_yf_semaphore():
                    full_df = await asyncio.wait_for(asyncio.to_thread(_fetch_batch_history, others, period, interval), timeout=15.0)

                for sym in others:
                    ticker_df = _extract_ticker_data(full_df, sym)
                    if ticker_df.empty:
                        # Fallback to Finviz
                        try:
                            f_data = await fetch_finviz_quotes([sym])
                            if sym.upper() in f_data:
                                q = f_data[sym.upper()]
                                data_str = f"### {sym}\n- **Price**: {q['price']:.2f}\n- **Volume**: {q['volume']:,}\n- **Source**: Finviz (Fallback)"
                                results.append(data_str)
                                history_cache[f"{sym}_{period}_{interval}"] = {"data": data_str, "last_updated": datetime.now(), "period": period, "interval": interval}
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

                    history_cache[f"{sym}_{period}_{interval}"] = {"data": data_str, "raw": raw_ohlcv, "last_updated": datetime.now(), "period": period, "interval": interval}
                    results.append(data_str)
            except TimeoutError:
                logger.error(f"Timeout: Fetch for {others} timed out.")
                results.append(f"### {others}\n- [ERROR]: Timeout during data retrieval.")
            except Exception as e:
                logger.error(f"Fetch error: {e}")
                results.append(f"### {others}\n- [ERROR]: {str(e)}")

    report = f"# Stock History Report\nGenerated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
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
    stale_time = now - timedelta(seconds=10)  # Immediately push past 5s boundary

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

        bar = bar_char * min(heat, 20)  # Cap bar length for UI
        if heat > 20:
            bar += "+"

        lines.append(f"| {sym} | {heat} | `{bar}` | {status} |")

    return "\n".join(lines)


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


async def _invalidate_market_cache(symbols: list[str] | None = None):
    """Core logic for market cache invalidation."""
    if not symbols:
        history_cache.clear()
        logger.info("[CACHE_ADMIN] Full market history cache invalidated.")
        return "The entire market cache has been successfully invalidated. All future requests will fetch fresh data from the internet."

    cleared = []
    for sym in symbols:
        norm = _normalize_ticker(sym)
        keys_to_delete = [k for k in history_cache.keys() if k.startswith(f"{norm}_")]
        for k in keys_to_delete:
            del history_cache[k]

        if keys_to_delete:
            cleared.append(norm)

    if not cleared:
        return f"Cache invalidation requested, but no existing cache entries were found for {symbols}."

    logger.info(f"[CACHE_ADMIN] Cache invalidated for symbols: {cleared}")
    return f"Cache successfully invalidated for: {', '.join(cleared)}."


@tool
async def invalidate_market_cache(symbols: list[str] | None = None) -> str:
    """
    Clears the internal memory cache for specified stock symbols to force a fresh data fetch.
    If 'symbols' is empty or None, it invalidates the ENTIRE market cache.
    Use this when the user explicitly asks for 'fresh', 'latest', or 'refresh' prices.
    """
    return await _invalidate_market_cache(symbols)


@tool
async def get_stock_quote(ticker: str, period: str = "1d", interval: str = "1m", use_fast_path: bool = True, use_finviz_fallback: bool = False, force_refresh: bool = False) -> dict[str, Any] | str:
    """Retrieve realtime or delayed stock quote for a specific ticker symbol. Fast-fetch skips full history parsing where possible.
    If 'use_finviz_fallback' is True, it strictly bypasses Yahoo Finance and fetches directly via the Finviz scraper module.
    If 'force_refresh' is True, it invalidates any existing cache for this symbol before fetching."""

    _ensure_worker_started()
    norm_ticker = _normalize_ticker(ticker)

    logger.info(f"[DIAGNOSTIC] get_stock_quote called for {ticker} | force_refresh={force_refresh} | use_fast_path={use_fast_path}")

    if force_refresh:
        logger.info(f"VLI_SYSTEM: Force refresh requested for {ticker}. Invalidating cache.")
        await _invalidate_market_cache([norm_ticker])

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
        cache_key = f"{norm_ticker}_{period}_{interval}"
        if cache_key in history_cache:
            entry = history_cache[cache_key]
            # [STABILITY] Accept data up to 120s old for immediate resonance
            age_sec = (datetime.now() - entry["last_updated"]).total_seconds()
            if age_sec < 120:
                logger.info(f"VLI Fast-Path: Warm cache hit for {norm_ticker} (Age: {age_sec:.1f}s)")
                # Extract price from the data_str or use a fallback
                try:
                    price_val = float(re.search(r"Close\*\*: (\d+\.?\d*)", entry["data"]).group(1))
                    return {"symbol": norm_ticker, "price": price_val, "change": 0.0, "is_cached": True}
                except Exception:
                    pass  # Fall through to fetch if parse fails

        # 2. Fast-Fetch Phase: Bypassing the global throttle lock for single-ticker quotes
        # 3. [Atomic Fast-Path] Lock-free fetch for sub-1s resonance
        # Forcing Fast-Path for standard tickers to avoid system-wide hangs
        if use_fast_path:
            logger.info(f"VLI Fast-Path: Starting lock-free fast-fetch for {norm_ticker}")
            try:
                # [STABILITY] 5s hard-timeout for all data retrieval threads
                t_obj = await asyncio.wait_for(asyncio.to_thread(yfinance.Ticker, norm_ticker, session=_get_session()), timeout=5.0)
                # Use faster 'fast_info' instead of full history
                fast = t_obj.fast_info

                # Check for mock data (Diagnostic check)
                if ticker.upper().startswith(("HIGH_", "MOD_", "INACT_")) or ticker.upper() == "MOCK_TICKER":
                    return {"symbol": ticker.upper(), "price": 100.0, "change": 0.0, "is_mock": True}

                return {
                    "symbol": norm_ticker,
                    "price": fast.last_price,
                    "change": ((fast.last_price / fast.previous_close) - 1) * 100 if fast.previous_close else 0.0,
                    "volume": getattr(fast, "last_volume", 0),  # Fast retrieval
                    "is_fast_fetch": True,
                }
            except Exception as fe:
                logger.warning(f"Fast-fetch failed for {norm_ticker}, falling back to batched fetch: {fe}")

        # 3. Standard Batched Fetch (Tier 3 fallback)
        # Consistent normalization (VIX -> ^VIX)
        # 5-second retrieval timeout to prevent VLI session hang (Aggressive Fail-Fast)
        data = await asyncio.wait_for(asyncio.to_thread(_fetch_batch_history, [norm_ticker], period, interval), timeout=5.0)

        # Extract using normalized ticker to ensure level-0 match
        ticker_df = _extract_ticker_data(data, norm_ticker)

        if ticker_df.empty:
            return f"[ERROR]: No data found for ticker '{ticker}' (normalized: {norm_ticker})."

        last_row = ticker_df.iloc[-1]

        # Ensure we have a valid price (DataFrame Close works even if .info fails)
        quote_price = float(last_row["Close"])

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
        df = await asyncio.to_thread(_fetch_stock_history, ticker, "1y", "1d")
        if df.empty:
            return f"[ERROR]: No data for {ticker}"

        returns = df["Close"].pct_change().dropna()
        if len(returns) < 20:
            return "Insufficient data for Sortino calculation."

        MAR = 0.0  # Minimum Acceptable Return (daily)
        downside = returns - MAR
        downside_squared = downside[downside < 0] ** 2
        downside_deviation = (downside_squared.sum() / len(returns)) ** 0.5

        if downside_deviation == 0:
            return f"Sortino Ratio ({ticker}): N/A (No downside volatility)"

        sortino = ((returns.mean() - MAR) / downside_deviation) * (252**0.5)
        return f"Sortino Ratio ({ticker}): {sortino:.2f}"
    except Exception as e:
        return f"[ERROR]: {str(e)}"


@tool
async def run_smc_analysis(ticker: str, interval: str = "auto") -> str:
    """
    SMC Specialist Primitive: Executes a professional ICT-based analysis using Multi-Timeframe Alignment
    by default (interval='auto'). If a specific interval is provided (e.g. '1h'), it will execute a
    single-pass isolated scanner.
    """
    import os
    import sys

    try:
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        try:
            from smartmoneyconcepts import smc
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout
    except ImportError:
        return "[ERROR]: The 'smartmoneyconcepts' library is required. Run 'pip install smartmoneyconcepts'."

    # Load configuration
    from src.config.smc_loader import load_smc_config

    config = load_smc_config()
    strategy = config.get("smc_strategy", {})

    norm_ticker = _normalize_ticker(ticker)

    # ==========================================
    # FALLBACK: Isolated Single-Pass Execution
    # ==========================================
    if interval.lower() != "auto":
        interval_norm = interval.lower()
        if interval_norm in ["1m", "2m", "5m", "15m"]:
            swing_length, period_needed = 20, "10d"
        elif interval_norm in ["1h", "4h", "2h"]:
            swing_length, period_needed = 10, "1mo"
        elif interval_norm in ["1d", "1wk"]:
            swing_length, period_needed = 5, "1y"
        else:
            swing_length, period_needed = 10, "1mo"

        history_samples = max(swing_length * 3, 100)
        logger.info(f"VLI SMC Analyst [CUSTOM OVERRIDE]: Executing {ticker} @ {interval}")

        try:
            data = await asyncio.wait_for(asyncio.to_thread(_fetch_batch_history, [norm_ticker], period_needed, interval), timeout=10.0)
            full_df = _extract_ticker_data(data, norm_ticker)
            if full_df.empty or len(full_df) < 10:
                return f"### {ticker} Analysis @ {interval}\n- [ERROR]: Insufficient data."

            df = full_df.tail(history_samples).copy()
            df.columns = [c.lower() for c in df.columns]

            swings = smc.swing_highs_lows(df, swing_length=swing_length)
            fvg = smc.fvg(df)
            ob = smc.ob(df, swings)
            structure = smc.bos_choch(df, swings)

            fvg_count = len(fvg[fvg["FVG"] != 0]) if "FVG" in fvg.columns else 0
            ob_count = len(ob[ob["OB"] != 0]) if "OB" in ob.columns else 0

            report = [f"## Custom Single-Pass SMC Analysis: {ticker} ({interval})", ""]
            last_struct = structure.iloc[-1]
            if last_struct.get("CHOCH") or last_struct.get("choch"):
                report.append("- **State**: ⚡ **Change of Character (ChoCh)** detected.")
            elif last_struct.get("BOS") or last_struct.get("bos"):
                report.append("- **State**: 📈 **Break of Structure (BOS)** confirmed.")
            else:
                report.append("- **State**: ⚖️ Stable market structure.")

            report.append(f"- **Order Blocks**: {ob_count} mapped.")
            report.append(f"- **FVGs**: {fvg_count} mapped.")
            report.append(f"\n**Current Price**: `${df['close'].iloc[-1]:.2f}`")
            return "\n".join(report)
        except Exception as e:
            return f"[ERROR]: Single-pass failed: {e}"

    # ==========================================
    # APEX 500 AUTONOMOUS MTF SCANNER
    # ==========================================
    logger.info(f"VLI SMC Analyst [MTF AUTONOMOUS SCAN]: Executing Apex 500 Alignment for {ticker}")
    report = [f"## MTF SMC Alignment Scan: {ticker} (Apex 500 Scanner)", ""]

    # 1. Macro Map (Trend Direction)
    macro_cfg = strategy.get("macro_map", {})
    macro_tf = macro_cfg.get("timeframes", ["1d"])[0]
    macro_lookback = macro_cfg.get("lookback_bars", 200)
    macro_period = "1y" if macro_tf in ("1d", "4h") else "6mo"

    macro_bias = "Neutral"
    try:
        mData = await asyncio.to_thread(_fetch_batch_history, [norm_ticker], macro_period, macro_tf)
        mDF = _extract_ticker_data(mData, norm_ticker).tail(macro_lookback).copy()
        if not mDF.empty:
            mDF.columns = [c.lower() for c in mDF.columns]
            mSwings = smc.swing_highs_lows(mDF, swing_length=15)
            mStruct = smc.bos_choch(mDF, mSwings)

            latest_bos = mStruct[mStruct["BOS"] != 0].tail(1)
            latest_choch = mStruct[mStruct["CHOCH"] != 0].tail(1)

            # Simple bias heuristic based on the latest structural event
            if not latest_choch.empty:
                macro_bias = "Bullish" if latest_choch["CHOCH"].iloc[-1] == 1 else "Bearish"
            elif not latest_bos.empty:
                macro_bias = "Bullish" if latest_bos["BOS"].iloc[-1] == 1 else "Bearish"

        report.append(f"### 1. Macro Map ({macro_tf})")
        report.append(f"- **Institutional Trend**: {macro_bias}")
    except Exception as e:
        report.append(f"### 1. Macro Map ({macro_tf})\n- [ERROR]: {e}")
        macro_bias = "Error"

    # 2. Tactical Map (Zones)
    tactical_cfg = strategy.get("tactical_map", {})
    tactical_tf = tactical_cfg.get("timeframes", ["1h"])[0]
    tactical_lookback = tactical_cfg.get("lookback_bars", 100)

    tactical_ready = False
    try:
        tData = await asyncio.to_thread(_fetch_batch_history, [norm_ticker], "1mo", tactical_tf)
        tDF = _extract_ticker_data(tData, norm_ticker).tail(tactical_lookback).copy()
        if not tDF.empty:
            tDF.columns = [c.lower() for c in tDF.columns]
            tSwings = smc.swing_highs_lows(tDF, swing_length=10)
            tOB = smc.ob(tDF, tSwings)
            tFVG = smc.fvg(tDF)

            ob_c = len(tOB[tOB["OB"] != 0]) if "OB" in tOB.columns else 0
            fvg_c = len(tFVG[tFVG["FVG"] != 0]) if "FVG" in tFVG.columns else 0
            tactical_ready = ob_c > 0 or fvg_c > 0

            report.append(f"### 2. Tactical Map ({tactical_tf})")
            report.append(f"- **Zones Mapped**: {ob_c} Order Blocks | {fvg_c} Fair Value Gaps.")
        else:
            report.append(f"### 2. Tactical Map ({tactical_tf})\n- Insufficient Data")
    except Exception as e:
        report.append(f"### 2. Tactical Map ({tactical_tf})\n- [ERROR]: {e}")

    # 3. Execution Trigger (Liquidity)
    trigger_cfg = strategy.get("execution_trigger", {})
    trigger_tf = trigger_cfg.get("timeframes", ["5m"])[0]
    trigger_lookback = trigger_cfg.get("lookback_bars", 50)

    sweep_aligned = False
    try:
        trData = await asyncio.to_thread(_fetch_batch_history, [norm_ticker], "5d", trigger_tf)
        trDF = _extract_ticker_data(trData, norm_ticker).tail(trigger_lookback).copy()
        if not trDF.empty:
            trDF.columns = [c.lower() for c in trDF.columns]
            trSwings = smc.swing_highs_lows(trDF, swing_length=5)
            # liquidity is tracked against swings
            trLiq = smc.liquidity(trDF, trSwings)

            liq_event = trLiq[trLiq["Liquidity"] != 0].tail(1)
            if not liq_event.empty:
                # 1 = Bullish Sweep (Sell-side liquidity grabbed), -1 = Bearish Sweep
                sweep_dir = "Bullish" if liq_event["Liquidity"].iloc[-1] == 1 else "Bearish"
                # Check MTF alignment
                if sweep_dir == macro_bias:
                    sweep_aligned = True

                report.append(f"### 3. Execution Trigger ({trigger_tf})")
                report.append(f"- **Liquidity Sweep**: YES ({sweep_dir})")
            else:
                report.append(f"### 3. Execution Trigger ({trigger_tf})")
                report.append("- **Liquidity Sweep**: NO (Accumulating)")
    except Exception as e:
        report.append(f"### 3. Execution Trigger ({trigger_tf})\n- [ERROR]: {e}")

    # 4. Authorization Matrix
    report.append("### 4. Apex Authorization Matrix")
    if sweep_aligned and tactical_ready:
        report.append("- **Status**: **[PASS]** Execution trigger aligns with MTF Institutional Macro trend.")
    else:
        report.append("- **Status**: **[FAIL]** Trigger does not align with Macro trend, or missing tactical structural zones.")

    return "\n".join(report)
