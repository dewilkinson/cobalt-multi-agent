# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Agent: Analyst - Exponential Moving Average trend analysis.
# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
import asyncio
import pandas as pd
from typing import List, Optional
from langchain_core.tools import tool
from .finance import _fetch_stock_history

from .shared_storage import ANALYST_CONTEXT

logger = logging.getLogger(__name__)

# Agent-specific resource context (Shared by Analyst sub-modules)
_NODE_RESOURCE_CONTEXT = ANALYST_CONTEXT



def calculate_ema(df: pd.DataFrame, periods: List[int]):
    """Calculates Exponential Moving Averages (EMA) for multiple periods."""
    for p in periods:
        df[f'ema_{p}'] = df['close'].ewm(span=p, adjust=False).mean()
    return df

@tool
async def get_ema_analysis(
    ticker: str, 
    periods: Optional[List[int]] = [20, 50, 200], 
    timespan: str = "1y", 
    interval: str = "1d"
) -> str:
    """
    Retrieves Exponential Moving Average (EMA) history for a stock ticker.
    Default periods are 20, 50, and 200. Default lookback is 1 year (1y) with daily (1d) interval.
    Useful for identifying trends and support/resistance levels.
    """
    def compute_ema(symbol: str, p_list: List[int], ts: str, intern: str):
        logger.info(f"Computing EMA history for {symbol} ({p_list}) over {ts}")
        df = _fetch_stock_history(symbol, ts, intern)

        if df.empty:
            return f"Error: No data found for ticker '{symbol}' to calculate EMA."
        
        # Standardize columns
        df.columns = [str(c).lower() for c in df.columns]
        df = calculate_ema(df, p_list)
        
        # Get the latest values
        last_row = df.iloc[-1]
        report = f"### EMA Analysis: {symbol.upper()} (Interval: {intern})\n\n"
        report += f"**Current Price:** {last_row['close']:.2f}\n\n"
        
        report += "#### Latest EMA Values:\n"
        for p in p_list:
            val = last_row[f'ema_{p}']
            status = "Above" if last_row['close'] > val else "Below"
            report += f"- **EMA {p}:** {val:.2f} (Price is {status} EMA)\n"
            
        if last_row.get(f'ema_20') is not None and last_row.get(f'ema_50') is not None and last_row.get(f'ema_200') is not None:
             if last_row['ema_20'] > last_row['ema_50'] > last_row['ema_200']:
                report += "\n📈 **Trend Sentiment:** Strong Bullish Alignment (20 > 50 > 200)."
             elif last_row['ema_20'] < last_row['ema_50'] < last_row['ema_200']:
                report += "\n📉 **Trend Sentiment:** Strong Bearish Alignment (20 < 50 < 200)."
            
        report += f"\n\n[EMA_DATA_FETCHED]: Sampled {len(df)} bars over the last {ts}."
        return report

    try:
        return await asyncio.wait_for(asyncio.to_thread(compute_ema, ticker, periods, timespan, interval), timeout=25.0)
    except Exception as e:
        logger.error(f"EMA Tool error: {str(e)}")
        return f"Error during EMA analysis: {str(e)}"
