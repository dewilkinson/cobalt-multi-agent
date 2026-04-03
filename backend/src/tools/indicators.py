# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Agent: Analyst - Technical indicators and momentum analysis.
# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
import asyncio
import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
from .finance import _fetch_stock_history

logger = logging.getLogger(__name__)

from .shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by Analyst sub-modules
_SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT



def calculate_rsi(df: pd.DataFrame, period: int = 14):
    """Calculates Relative Strength Index (RSI)."""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
    """Calculates Moving Average Convergence Divergence (MACD)."""
    df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = df['ema_fast'] - df['ema_slow']
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    return df

def calculate_atr(df: pd.DataFrame, period: int = 14):
    """Calculates Average True Range (ATR)."""
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['atr'] = true_range.rolling(window=period).mean()
    return df

@tool
async def get_rsi_analysis(ticker: str, period: str = "60d", interval: str = "1d") -> str:
    """
    Primitive: Retrieves the Relative Strength Index (RSI) for a ticker.
    Used for detecting overbought (>70) or oversold (<30) conditions.
    """
    def compute(symbol, p, i):
        df = _fetch_stock_history(symbol, p, i)
        if df.empty: return f"### RSI: {symbol.upper()}\nError: No data for p={p}, i={i}\n"

        df.columns = [str(c).lower() for c in df.columns]
        df = calculate_rsi(df)
        val = df['rsi'].iloc[-1]
        status = "Overbought" if val > 70 else "Oversold" if val < 30 else "Neutral"
        return f"### RSI: {symbol.upper()} ({i})\n- **Value:** {val:.2f}\n- **Stance:** {status}\n"

    return await asyncio.to_thread(compute, ticker, period, interval)

@tool
async def get_macd_analysis(ticker: str, period: str = "60d", interval: str = "1d") -> str:
    """
    Primitive: Retrieves MACD history and crossover signals.
    Used for identifying momentum shifts and trend reversals.
    """
    def compute(symbol: str, p: str, i: str):
        df = _fetch_stock_history(symbol, p, i)
        if df.empty: return f"### MACD: {symbol.upper()}\nError: No data for p={p}, i={i}\n"

        df.columns = [str(c).lower() for c in df.columns]
        df = calculate_macd(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        crossover = "Bullish Cross" if (last['macd'] > last['macd_signal'] and prev['macd'] < prev['macd_signal']) else \
                    "Bearish Cross" if (last['macd'] < last['macd_signal'] and prev['macd'] > prev['macd_signal']) else "No Cross"
        return f"### MACD: {symbol.upper()} ({i})\n- **MACD:** {last['macd']:.3f}\n- **Signal:** {last['macd_signal']:.3f}\n- **Momentum:** {crossover}\n"

    return await asyncio.to_thread(compute, ticker, period, interval)

@tool
async def get_volatility_atr(ticker: str, period: str = "60d", interval: str = "1d") -> str:
    """
    Primitive: Retrieves Average True Range (ATR).
    Used for determining stop-loss distances and market volatility.
    """
    def compute(symbol: str, p: str, i: str):
        df = _fetch_stock_history(symbol, p, i)
        if df.empty: return f"### Volatility (ATR): {symbol.upper()}\nError: No data for p={p}, i={i}\n"

        df.columns = [str(c).lower() for c in df.columns]
        df = calculate_atr(df)
        val = df['atr'].iloc[-1]
        return f"### Volatility (ATR): {symbol.upper()} ({i})\n- **ATR:** {val:.2f} (Current range expectation)\n"

    try:
        return await asyncio.wait_for(asyncio.to_thread(compute, ticker, period, interval), timeout=20.0)
    except Exception as e:
        logger.error(f"Volatility (ATR) tool error: {str(e)}")
        return f"Error: {str(e)}"

@tool
async def get_bollinger_bands(ticker: str, period: str = "60d", interval: str = "1d") -> str:
    """
    Calculate Bollinger Bands for a given ticker (20-day SMA +/- 2 std devs).
    Identifies overbought (price > upper) and oversold (price < lower) conditions.
    """
    def compute_bb(symbol: str, p: str, i: str):
        df = _fetch_stock_history(symbol, p, i)

        if df.empty:
            return f"Error: No data found for ticker '{symbol}' with period '{p}' and interval '{i}'."
        
        df.columns = [str(c).lower() for c in df.columns]
        
        # Calculate SMA 20
        df['sma20'] = df['close'].rolling(window=20).mean()
        # Calculate Standard Deviation
        df['std'] = df['close'].rolling(window=20).std()
        # Calculate Upper/Lower Bands
        df['upper'] = df['sma20'] + (df['std'] * 2)
        df['lower'] = df['sma20'] - (df['std'] * 2)
        
        current_price = df['close'].iloc[-1]
        upper = df['upper'].iloc[-1]
        lower = df['lower'].iloc[-1]
        mid = df['sma20'].iloc[-1]
        
        status = "Neutral"
        if current_price > upper:
            status = "Overbought (Above Upper Band)"
        elif current_price < lower:
            status = "Oversold (Below Lower Band)"
        elif current_price > mid:
            status = "Bullish (Above Middle Band)"
        else:
            status = "Bearish (Below Middle Band)"
            
        report = f"### Bollinger Bands Analysis: {symbol.upper()} ({i})\n"
        report += f"| Metric | Value |\n"
        report += f"| :--- | :--- |\n"
        report += f"| **Current Price** | {current_price:.2f} |\n"
        report += f"| **Upper Band** | {upper:.2f} |\n"
        report += f"| **Middle Band (SMA20)** | {mid:.2f} |\n"
        report += f"| **Lower Band** | {lower:.2f} |\n"
        report += f"| **Status** | **{status}** |\n"
        
        return report

    try:
        return await asyncio.wait_for(asyncio.to_thread(compute_bb, ticker, period, interval), timeout=20.0)
    except Exception as e:
        logger.error(f"Bollinger Bands tool error: {str(e)}")
        return f"Error: {str(e)}"

@tool
async def get_volume_profile(ticker: str, period: str = "60d", interval: str = "1d") -> str:
    """
    Primitive: Simplified Volume-at-Price profile.
    Identifies high-volume nodes where price is likely to find support/resistance.
    """
    def compute_vp(symbol: str, p: str, i: str):
        df = _fetch_stock_history(symbol, p, i)
        if df.empty: return f"### Volume Profile: {symbol.upper()}\nError: No data for p={p}, i={i}\n"
        
        df.columns = [str(c).lower() for c in df.columns]
        # Bins for price levels
        bins = np.linspace(df['low'].min(), df['high'].max(), 10)
        df['price_bin'] = pd.cut(df['close'], bins=bins)
        profile = df.groupby('price_bin')['volume'].sum()
        poc = profile.idxmax() # Point of Control
        return f"### Volume Profile: {symbol.upper()} ({i})\n- **Highest Volume Node (POC):** {poc}\n"

    return await asyncio.to_thread(compute_vp, ticker, period, interval)

def calculate_downside_deviation(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Calculates downside deviation for Sortino Ratio."""
    excess_returns = returns - risk_free_rate
    downside_returns = excess_returns.copy()
    downside_returns[excess_returns > 0] = 0.0
    return np.sqrt(np.mean(downside_returns**2))

@tool
async def get_sharpe_ratio(ticker: str, target_price: float = 0.0, period: str = "20d", interval: str = "1d") -> str:
    """
    Primitive: Calculates the Sharpe Ratio for a ticker using the 10Y Yield (.TNX) as the risk-free rate.
    Uses target_price for the Expected Return if provided > 0.0, otherwise calculates historical Sharpe.
    """
    def compute(symbol, t_price, p, i):
        try:
            df = _fetch_stock_history(symbol, p, i)
            if df.empty: return f"Error: No data for {symbol}"
            
            # Risk free rate from TNX geometry or fallback 4.28%
            import yfinance as yf
            rf = 0.0428
            try:
                tnx = yf.Ticker("^TNX").history(period="1d")
                if not tnx.empty: rf = tnx['Close'].iloc[-1] / 100.0
            except:
                pass
                
            df.columns = [str(c).lower() for c in df.columns]
            current_price = df['close'].iloc[-1]
            returns = df['close'].pct_change().dropna()
            
            if t_price and t_price > 0.0:
                # Projected Sharpe: S = (Target_Return - Rf) / Realized_Volatility
                target_return = (t_price - current_price) / current_price
                vol = returns.std()
                s = (target_return - rf) / (vol if vol > 0 else 0.0001)
                return f"### Projected Sharpe Ratio: {symbol.upper()}\n- Target Price: ${t_price:.2f}\n- Current: ${current_price:.2f}\n- Projected Return: {target_return*100:.2f}%\n- Risk-Free (.TNX): {rf*100:.2f}%\n- Volatility (20-day σ): {vol*100:.2f}%\n- **Sharpe Ratio (S):** {s:.2f}"
            else:
                # Historical Annualized
                avg_return = returns.mean()
                vol = returns.std()
                daily_rf = rf / 252.0
                s_historical = ((avg_return - daily_rf) / vol) * np.sqrt(252)
                return f"### Historical Sharpe Ratio: {symbol.upper()}\n- Historical Volatility: {vol*100:.2f}%\n- Risk-Free (.TNX): {rf*100:.2f}%\n- **Historical Sharpe:** {s_historical:.2f}"
                
        except Exception as e:
            return f"Error computing Sharpe for {symbol}: {e}"
            
    return await asyncio.to_thread(compute, ticker, target_price, period, interval)

@tool
async def get_sortino_ratio(ticker: str, target_price: float = 0.0, period: str = "20d", interval: str = "1d") -> str:
    """
    Primitive: Calculates the Sortino Ratio for a ticker using the 10Y Yield (.TNX) as the risk-free rate.
    Uses target_price for the Expected Return if provided > 0.0, otherwise calculates historical Sortino.
    Preferred over Sharpe as it only penalizes downside volatility.
    """
    def compute(symbol, t_price, p, i):
        try:
            df = _fetch_stock_history(symbol, p, i)
            if df.empty: return f"Error: No data for {symbol}"
            
            import yfinance as yf
            rf = 0.0428
            try:
                tnx = yf.Ticker("^TNX").history(period="1d")
                if not tnx.empty: rf = tnx['Close'].iloc[-1] / 100.0
            except:
                pass
                
            df.columns = [str(c).lower() for c in df.columns]
            current_price = df['close'].iloc[-1]
            returns = df['close'].pct_change().dropna()
            downside_dev = calculate_downside_deviation(returns, rf / 252.0)
            
            if t_price and t_price > 0.0:
                # Projected Sortino
                target_return = (t_price - current_price) / current_price
                s = (target_return - rf) / (downside_dev if downside_dev > 0 else 0.0001)
                return f"### Projected Sortino Ratio: {symbol.upper()}\n- Target Price: ${t_price:.2f}\n- Current: ${current_price:.2f}\n- Projected Return: {target_return*100:.2f}%\n- Risk-Free (.TNX): {rf*100:.2f}%\n- Downside Dev (σ_d): {downside_dev*100:.2f}%\n- **Sortino Ratio (S_d):** {s:.2f}"
            else:
                # Historical Annualized
                avg_return = returns.mean()
                daily_rf = rf / 252.0
                s_historical = ((avg_return - daily_rf) / downside_dev) * np.sqrt(252) if downside_dev > 0 else 0
                return f"### Historical Sortino Ratio: {symbol.upper()}\n- Downside Dev: {downside_dev*100:.2f}%\n- Risk-Free (.TNX): {rf*100:.2f}%\n- **Historical Sortino:** {s_historical:.2f}"
                
        except Exception as e:
            return f"Error computing Sortino for {symbol}: {e}"
            
    return await asyncio.to_thread(compute, ticker, target_price, period, interval)
