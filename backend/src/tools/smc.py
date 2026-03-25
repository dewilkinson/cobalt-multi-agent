# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
import asyncio
import yfinance as yf
import pandas as pd
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

def detect_fvg(df: pd.DataFrame):
    """Detects Fair Value Gaps (FVG)."""
    fvgs = []
    # Needs at least 3 candles to find a gap
    for i in range(2, len(df)):
        # Bullish FVG
        if df['high'].iloc[i-2] < df['low'].iloc[i]:
            fvgs.append({
                "type": "Bullish",
                "top": df['low'].iloc[i],
                "bottom": df['high'].iloc[i-2],
                "date": df.index[i].strftime('%Y-%m-%d')
            })
        # Bearish FVG
        elif df['low'].iloc[i-2] > df['high'].iloc[i]:
            fvgs.append({
                "type": "Bearish",
                "top": df['low'].iloc[i-2],
                "bottom": df['high'].iloc[i],
                "date": df.index[i].strftime('%Y-%m-%d')
            })
    return fvgs

def detect_structure(df: pd.DataFrame):
    """Simple BOS detection."""
    # Find local swing highs/lows
    # Simplification: Use rolling window to find relative peaks
    window = 10
    df['peak_high'] = df['high'].rolling(window=window, center=True).max()
    df['peak_low'] = df['low'].rolling(window=window, center=True).min()
    
    breaks = []
    current_trend = None
    
    for i in range(window, len(df)):
        # Check for break of historical peak high
        past_peak_high = df['peak_high'].iloc[i-window:i].max()
        if df['close'].iloc[i] > past_peak_high:
            if current_trend != "Bullish":
                breaks.append({"type": "BOS (Bullish)", "date": df.index[i].strftime('%Y-%m-%d')})
                current_trend = "Bullish"
        
        # Check for break of historical peak low
        past_peak_low = df['peak_low'].iloc[i-window:i].min()
        if df['close'].iloc[i] < past_peak_low:
            if current_trend != "Bearish":
                breaks.append({"type": "BOS (Bearish)", "date": df.index[i].strftime('%Y-%m-%d')})
                current_trend = "Bearish"
                
    return breaks

@tool
async def get_smc_analysis(ticker: str, period: str = "60d", interval: str = "1d") -> str:
    """
    Perform Smart Money Concepts (SMC) technical analysis on a given ticker.
    Detects Fair Value Gaps (FVG) and Market Structure (BOS).
    Best for finding high-probability reversal and continuation zones.
    
    Args:
        ticker: The stock ticker symbol.
        period: The lookback period (e.g., '60d', '1mo', '1y').
        interval: The timeframe interval (e.g., '1h', '1d', '1wk').
    """
    def compute_smc(symbol: str, p: str, i: str):
        logger.info(f"Computing custom SMC analysis for {symbol} (p={p}, i={i})")
        stock = yf.Ticker(symbol)
        df = stock.history(period=p, interval=i)
        if df.empty:
            return f"Error: No data found for ticker '{symbol}' with period '{p}' and interval '{i}'."
        
        df.columns = [c.lower() for c in df.columns]
        
        fvgs = detect_fvg(df)
        breaks = detect_structure(df)
        
        report = f"### SMC Technical Scan: {symbol.upper()} (Timeframe: {i})\n\n"
        
        # Structure
        if breaks:
            latest_bos = breaks[-1]
            report += f"✅ **Market Structure:** {latest_bos['type']} detected on {latest_bos['date']}.\n"
        else:
            report += f"⚪ **Market Structure:** Ranging. No significant structure breaks detected in the last {p}.\n"
            
        # Gaps
        recent_fvgs = fvgs[-3:] if fvgs else []
        if recent_fvgs:
            report += f"📊 **Fair Value Gaps (FVG):** Found {len(fvgs)} total imbalances. Recent gaps:\n"
            for f in recent_fvgs:
                report += f"  - {f['type']} FVG on {f['date']} between {f['bottom']:.2f} and {f['top']:.2f}\n"
        else:
            report += "⚪ **Fair Value Gaps:** No significant open gaps found in recent price action.\n"
            
        report += f"\n*Current Price: {df['close'].iloc[-1]:.2f}*"
        return report

    try:
        return await asyncio.wait_for(asyncio.to_thread(compute_smc, ticker, period, interval), timeout=25.0)
    except Exception as e:
        logger.error(f"Custom SMC Tool error: {str(e)}")
        return f"Error during SMC analysis: {str(e)}"
