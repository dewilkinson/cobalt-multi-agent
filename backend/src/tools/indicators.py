# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
import asyncio
import yfinance as yf
import pandas as pd
import numpy as np
from typing import List, Optional
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

def calculate_rsi(df: pd.DataFrame, period: int = 14):
    """Calculates Relative Strength Index (RSI)."""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
    """Calculates Moving Average Convergence Divergence (MACD)."""
    df['EMA_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['EMA_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['MACD'] = df['EMA_fast'] - df['EMA_slow']
    df['MACD_signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    return df

def calculate_atr(df: pd.DataFrame, period: int = 14):
    """Calculates Average True Range (ATR)."""
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['ATR'] = true_range.rolling(window=period).mean()
    return df

@tool
async def get_rsi_analysis(ticker: str) -> str:
    """
    Primitive: Retrieves the Relative Strength Index (RSI) for a ticker.
    Used for detecting overbought (>70) or oversold (<30) conditions.
    """
    def compute(symbol: str):
        stock = yf.Ticker(symbol)
        df = stock.history(period="60d")
        if df.empty: return "Error: No data"
        df.columns = [c.lower() for c in df.columns]
        df = calculate_rsi(df)
        val = df['RSI'].iloc[-1]
        status = "Overbought" if val > 70 else "Oversold" if val < 30 else "Neutral"
        return f"### RSI: {symbol.upper()}\n- **Value:** {val:.2f}\n- **Stance:** {status}\n"

    return await asyncio.to_thread(compute, ticker)

@tool
async def get_macd_analysis(ticker: str) -> str:
    """
    Primitive: Retrieves MACD history and crossover signals.
    Used for identifying momentum shifts and trend reversals.
    """
    def compute(symbol: str):
        stock = yf.Ticker(symbol)
        df = stock.history(period="60d")
        if df.empty: return "Error: No data"
        df.columns = [c.lower() for c in df.columns]
        df = calculate_macd(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        crossover = "Bullish Cross" if (last['MACD'] > last['MACD_signal'] and prev['MACD'] < prev['MACD_signal']) else \
                    "Bearish Cross" if (last['MACD'] < last['MACD_signal'] and prev['MACD'] > prev['MACD_signal']) else "No Cross"
        return f"### MACD: {symbol.upper()}\n- **MACD:** {last['MACD']:.3f}\n- **Signal:** {last['MACD_signal']:.3f}\n- **Momentum:** {crossover}\n"

    return await asyncio.to_thread(compute, ticker)

@tool
async def get_volatility_atr(ticker: str) -> str:
    """
    Primitive: Retrieves Average True Range (ATR).
    Used for determining stop-loss distances and market volatility.
    """
    def compute(symbol: str):
        stock = yf.Ticker(symbol)
        df = stock.history(period="60d")
        if df.empty: return "Error: No data"
        df.columns = [c.lower() for c in df.columns]
        df = calculate_atr(df)
        val = df['ATR'].iloc[-1]
        return f"### Volatility (ATR): {symbol.upper()}\n- **ATR:** {val:.2f} (Current range expectation)\n"

    return await asyncio.to_thread(compute, ticker)

@tool
async def get_volume_profile(ticker: str) -> str:
    """
    Primitive: Simplified Volume-at-Price profile.
    Identifies high-volume nodes where price is likely to find support/resistance.
    """
    def compute(symbol: str):
        stock = yf.Ticker(symbol)
        df = stock.history(period="60d")
        if df.empty: return "Error: No data"
        # Bins for price levels
        bins = np.linspace(df['Low'].min(), df['High'].max(), 10)
        df['PriceBin'] = pd.cut(df['Close'], bins=bins)
        profile = df.groupby('PriceBin')['Volume'].sum()
        poc = profile.idxmax() # Point of Control
        return f"### Volume Profile: {symbol.upper()}\n- **Highest Volume Node (POC):** {poc}\n"

    return await asyncio.to_thread(compute, ticker)
