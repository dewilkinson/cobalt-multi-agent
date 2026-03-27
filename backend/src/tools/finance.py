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

# 3. Global context
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

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
        data = yf.download(
            tickers=tickers,
            period=period,
            interval=interval,
            group_by='ticker',
            session=session,
            progress=False,
            threads=False # Maintain throttle integrity
        )
        
        # Hard delay to prevent rate limiting
        time.sleep(1.0)
        return data

# Backward compatibility alias
_fetch_stock_history = _fetch_batch_history

def _extract_ticker_data(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Helper to extract a single ticker's dataframe from a multi-index yf.download result."""
    if ticker in df.columns.levels[0]:
        return df[ticker].dropna()
    return pd.DataFrame()

@tool
async def get_symbol_history_data(symbols: List[str], period: str = "1d", interval: str = "1h") -> str:
    """
    Scout Primitive: Retrieve stock history for multiple symbols in a single batched request.
    """
    logger.info(f"Scout fetching history for {symbols}")
    
    # Check cache
    history_cache = _NODE_RESOURCE_CONTEXT.setdefault("history_cache", {})
    cache_key = f"{','.join(sorted(symbols))}_{period}_{interval}"
    if cache_key in history_cache:
        return history_cache[cache_key]
    
    try:
        # Batch Fetch
        full_df = await asyncio.to_thread(_fetch_batch_history, symbols, period, interval)
        
        results = []
        for sym in symbols:
            # Handle both single-ticker and multi-ticker return types from yf.download
            if len(symbols) > 1:
                ticker_df = _extract_ticker_data(full_df, sym)
            else:
                ticker_df = full_df.dropna()

            if ticker_df.empty:
                results.append(f"### {sym}\n- [ERROR]: No data found.")
                continue

            last_row = ticker_df.iloc[-1]
            results.append(f"""
### {sym.upper()}
- **Period**: {period} | **Interval**: {interval}
- **Close**: {float(last_row['Close']):.2f}
- **High**: {float(last_row['High']):.2f}
- **Low**: {float(last_row['Low']):.2f}
- **Volume**: {int(last_row['Volume']):,}
""")
        
        report = f"# Stock History Report\nGenerated at {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        report += "\n".join(results)
        
        if "[ERROR]" not in report:
            history_cache[cache_key] = report.strip()
            
        return report.strip()
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return f"[ERROR]: Failed to fetch history batch: {str(e)}"


@tool
async def get_stock_quote(ticker: str, period: str = "5d", interval: str = "1d") -> Union[Dict[str, Any], str]:
    """
    Get current stock quote and OHLC data using the batched fetcher.
    """
    try:
        data = await asyncio.to_thread(_fetch_batch_history, [ticker], period, interval)
        ticker_df = _extract_ticker_data(data, ticker)
        
        if ticker_df.empty:
            return f"[ERROR]: No data found for ticker '{ticker}'."
        
        last_row = ticker_df.iloc[-1]
        
        # Build report
        report = f"""
[TECHNICAL_LOG]
Status: SUCCESS
Parameters: {{'ticker': '{ticker}', 'period': '{period}', 'interval': '{interval}'}}

[OHLC_DATA]
Symbol: {ticker.upper()}
Open: {float(last_row['Open']):.2f}
High: {float(last_row['High']):.2f}
Low: {float(last_row['Low']):.2f}
Close: {float(last_row['Close']):.2f}
Current: {float(last_row['Close']):.2f}
Volume: {int(last_row['Volume'])}
"""
        return report.strip()
    except Exception as e:
        return f"[ERROR]: {str(e)}"

@tool
async def get_sharpe_ratio(ticker: str, period: str = "1y") -> str:
    """Calculate Sharpe ratio using batched fetching for the ticker and risk-free benchmark."""
    try:
        # Batch fetch both the ticker and the 10Y Yield proxy
        full_df = await asyncio.to_thread(_fetch_batch_history, [ticker, "^TNX"], period, "1d")
        
        ticker_df = _extract_ticker_data(full_df, ticker)
        tnx_df = _extract_ticker_data(full_df, "^TNX")

        if ticker_df.empty: return f"### Sharpe: {ticker.upper()}\n[ERROR]: No ticker data."
        
        # Calculate risk-free rate from ^TNX if available, else 4.3%
        rf_rate = 0.043
        if not tnx_df.empty:
            rf_rate = float(tnx_df.iloc[-1]['Close']) / 100.0
            
        returns = ticker_df['Close'].pct_change().dropna()
        excess_returns = returns - (rf_rate / 252)
        sharpe = (excess_returns.mean() / excess_returns.std()) * (252**0.5)
        return f"### Sharpe Ratio: {ticker.upper()}\n- **Value:** {sharpe:.2f}\n"
    except Exception as e:
        return f"### Sharpe Ratio: {ticker.upper()}\n[ERROR]: {str(e)}"

@tool
async def get_sortino_ratio(ticker: str, period: str = "1y") -> str:
    """Calculate Sortino ratio using batched fetching."""
    try:
        full_df = await asyncio.to_thread(_fetch_batch_history, [ticker, "^TNX"], period, "1d")
        
        ticker_df = _extract_ticker_data(full_df, ticker)
        tnx_df = _extract_ticker_data(full_df, "^TNX")

        if ticker_df.empty: return f"### Sortino: {ticker.upper()}\n[ERROR]: No ticker data."
        
        rf_rate = 0.043
        if not tnx_df.empty:
            rf_rate = float(tnx_df.iloc[-1]['Close']) / 100.0
            
        returns = ticker_df['Close'].pct_change().dropna()
        excess_returns = returns - (rf_rate / 252)
        downside_returns = excess_returns[excess_returns < 0]
        downside_std = downside_returns.std() * (252**0.5)
        sortino = (excess_returns.mean() * 252) / downside_std if downside_std != 0 else 0
        return f"### Sortino Ratio: {ticker.upper()}\n- **Value:** {sortino:.2f}\n"
    except Exception as e:
        return f"### Sortino Ratio: {ticker.upper()}\n[ERROR]: {str(e)}"
