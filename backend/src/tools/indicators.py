# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Agent: Analyst - Technical indicators and momentum analysis.
# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import asyncio
import json
import logging
import os
from typing import Any

import numpy as np
import pandas as pd
import pandas_ta as ta
from langchain_core.tools import tool

from .finance import _fetch_stock_history

logger = logging.getLogger(__name__)

from .shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context: Persistent, shared by Analyst sub-modules
_SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


def calculate_rsi(df: pd.DataFrame, period: int = 14):
    """Calculates Relative Strength Index (RSI)."""
    df.ta.rsi(length=period, append=True)
    # pandas_ta auto-names columns, typically 'RSI_14'
    rsi_col = [col for col in df.columns if col.startswith("RSI")][0]
    df["rsi"] = df[rsi_col]
    return df


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
    """Calculates Moving Average Convergence Divergence (MACD)."""
    df.ta.macd(fast=fast, slow=slow, signal=signal, append=True)
    try:
        macd_col = [col for col in df.columns if col.startswith("MACD_")][0]
        macds_col = [col for col in df.columns if col.startswith("MACDs_")][0]
        macdh_col = [col for col in df.columns if col.startswith("MACDh_")][0]
        df["macd"] = df[macd_col]
        df["macd_signal"] = df[macds_col]
        df["macd_hist"] = df[macdh_col]
    except IndexError:
        # Fallback if pandas_ta failed to append the indicator columns
        df["macd"] = 0.0
        df["macd_signal"] = 0.0
        df["macd_hist"] = 0.0
    return df


def calculate_atr(df: pd.DataFrame, period: int = 14):
    """Calculates Average True Range (ATR)."""
    df.ta.atr(length=period, append=True)
    atr_col = [col for col in df.columns if col.startswith("ATRr_")][0]
    df["atr"] = df[atr_col]
    return df


@tool
async def get_rsi_analysis(ticker: str, period: str = "", interval: str = "") -> str:
    """
    Primitive: Retrieves the Relative Strength Index (RSI) for a ticker.
    Used for detecting overbought (>70) or oversold (<30) conditions.
    """

    def compute(symbol, p, i):
        if not p:
            is_day_trading = os.getenv("VLI_TRADING_STYLE", "day_trading") == "day_trading"
            p, i = ("2d", "5m") if is_day_trading else ("60d", "1d")
            
        df = _fetch_stock_history(symbol, p, i)
        if df.empty:
            return f"### RSI: {symbol.upper()}\nError: No data for p={p}, i={i}\n"

        df.columns = [str(c).lower() for c in df.columns]
        df = calculate_rsi(df)
        val = df["rsi"].iloc[-1]
        status = "Overbought" if val > 70 else "Oversold" if val < 30 else "Neutral"
        return f"### RSI: {symbol.upper()} ({i})\n- **Value:** {val:.2f}\n- **Stance:** {status}\n"

    return await asyncio.to_thread(compute, ticker, period, interval)


@tool
async def get_macd_analysis(ticker: str, period: str = "", interval: str = "") -> str:
    """
    Primitive: Retrieves MACD history and crossover signals.
    Used for identifying momentum shifts and trend reversals.
    """

    def compute(symbol: str, p: str, i: str):
        if not p:
            is_day_trading = os.getenv("VLI_TRADING_STYLE", "day_trading") == "day_trading"
            p, i = ("2d", "5m") if is_day_trading else ("60d", "1d")
            
        df = _fetch_stock_history(symbol, p, i)
        if df.empty:
            return f"### MACD: {symbol.upper()}\nError: No data for p={p}, i={i}\n"

        df.columns = [str(c).lower() for c in df.columns]
        df = calculate_macd(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        crossover = "Bullish Cross" if (last["macd"] > last["macd_signal"] and prev["macd"] < prev["macd_signal"]) else "Bearish Cross" if (last["macd"] < last["macd_signal"] and prev["macd"] > prev["macd_signal"]) else "No Cross"
        return f"### MACD: {symbol.upper()} ({i})\n- **MACD:** {last['macd']:.3f}\n- **Signal:** {last['macd_signal']:.3f}\n- **Momentum:** {crossover}\n"

    return await asyncio.to_thread(compute, ticker, period, interval)


@tool
async def get_volatility_atr(ticker: str, period: str = "", interval: str = "") -> str:
    """
    Primitive: Retrieves Average True Range (ATR).
    Used for determining stop-loss distances and market volatility.
    """

    def compute(symbol: str, p: str, i: str):
        if not p:
            is_day_trading = os.getenv("VLI_TRADING_STYLE", "day_trading") == "day_trading"
            p, i = ("2d", "5m") if is_day_trading else ("60d", "1d")
            
        df = _fetch_stock_history(symbol, p, i)
        if df.empty:
            return f"### Volatility (ATR): {symbol.upper()}\nError: No data for p={p}, i={i}\n"

        df.columns = [str(c).lower() for c in df.columns]
        df = calculate_atr(df)
        val = df["atr"].iloc[-1]
        return f"### Volatility (ATR): {symbol.upper()} ({i})\n- **ATR:** {val:.2f} (Current range expectation)\n"

    try:
        return await asyncio.wait_for(asyncio.to_thread(compute, ticker, period, interval), timeout=20.0)
    except Exception as e:
        logger.error(f"Volatility (ATR) tool error: {str(e)}")
        return f"Error: {str(e)}"


@tool
async def get_bollinger_bands(ticker: str, period: str = "", interval: str = "") -> str:
    """
    Calculate Bollinger Bands for a given ticker (20-day SMA +/- 2 std devs).
    Identifies overbought (price > upper) and oversold (price < lower) conditions.
    """

    def compute_bb(symbol: str, p: str, i: str):
        if not p:
            is_day_trading = os.getenv("VLI_TRADING_STYLE", "day_trading") == "day_trading"
            p, i = ("2d", "5m") if is_day_trading else ("60d", "1d")
            
        df = _fetch_stock_history(symbol, p, i)

        if df.empty:
            return f"Error: No data found for ticker '{symbol}' with period '{p}' and interval '{i}'."

        df.columns = [str(c).lower() for c in df.columns]

        # Calculate SMA 20
        df["sma20"] = df["close"].rolling(window=20).mean()
        # Calculate Standard Deviation
        df["std"] = df["close"].rolling(window=20).std()
        # Calculate Upper/Lower Bands
        df["upper"] = df["sma20"] + (df["std"] * 2)
        df["lower"] = df["sma20"] - (df["std"] * 2)

        current_price = df["close"].iloc[-1]
        upper = df["upper"].iloc[-1]
        lower = df["lower"].iloc[-1]
        mid = df["sma20"].iloc[-1]

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
        report += "| Metric | Value |\n"
        report += "| :--- | :--- |\n"
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
    Primitive: Institutional-grade Volume-at-Price (VP) profile.
    Calculates Point of Control (POC) and Value Area (VAH/VAL) containing 70% of total volume.
    Returns a structured JSON with metadata and 24-node distribution.
    """

    def compute_vp(symbol: str, p: str, i: str):
        df = _fetch_stock_history(symbol, p, i)
        if df.empty:
            return f"### Volume Profile: {symbol.upper()}\nError: No data for p={p}, i={i}\n"

        df.columns = [str(c).lower() for c in df.columns]
        
        try:
            # 1. Base Aggregation (24 Nodes for high-fidelity)
            bins = np.linspace(df["low"].min(), df["high"].max(), 25) # 25 edges = 24 bins
            bin_vols = np.zeros(24)

            # Distribute tracking volume symmetrically across the candle range
            for _, row in df.iterrows():
                high = row['high']
                low = row['low']
                vol = row['volume']
                
                if high > low:
                    for i in range(24):
                        bin_low = bins[i]
                        bin_high = bins[i+1]
                        if high < bin_low or low > bin_high:
                            continue
                        
                        overlap_high = min(high, bin_high)
                        overlap_low = max(low, bin_low)
                        fraction = (overlap_high - overlap_low) / (high - low)
                        bin_vols[i] += vol * fraction
                else:
                    for i in range(24):
                         if low >= bins[i] and low <= bins[i+1]:
                             bin_vols[i] += vol

            # Convert bins to readable ranges
            nodes = []
            for i in range(24):
                nodes.append({
                    "low": float(bins[i]),
                    "high": float(bins[i+1]),
                    "volume": float(bin_vols[i]),
                    "is_poc": False,
                    "is_va": False
                })

            if not nodes:
                return f"Error: No specific nodes could be constructed for {symbol}."

            # 2. Identify Point of Control (POC)
            total_volume = sum(n["volume"] for n in nodes)
            poc_idx = 0
            max_vol = -1
            for idx, n in enumerate(nodes):
                if n["volume"] > max_vol:
                    max_vol = n["volume"]
                    poc_idx = idx
            
            nodes[poc_idx]["is_poc"] = True
            poc_price = (nodes[poc_idx]["low"] + nodes[poc_idx]["high"]) / 2

            # 3. Calculate Value Area (70% Volume Expansion)
            target_vol = total_volume * 0.70
            current_vol = nodes[poc_idx]["volume"]
            nodes[poc_idx]["is_va"] = True
            
            up_idx = poc_idx + 1
            down_idx = poc_idx - 1
            
            while current_vol < target_vol and (up_idx < len(nodes) or down_idx >= 0):
                up_vol = nodes[up_idx]["volume"] if up_idx < len(nodes) else -1
                down_vol = nodes[down_idx]["volume"] if down_idx >= 0 else -1
                
                if up_vol >= down_vol and up_vol != -1:
                    current_vol += up_vol
                    nodes[up_idx]["is_va"] = True
                    up_idx += 1
                elif down_vol != -1:
                    current_vol += down_vol
                    nodes[down_idx]["is_va"] = True
                    down_idx -= 1
                else:
                    break

            # Identify VAH/VAL boundaries
            va_nodes = [n for n in nodes if n["is_va"]]
            vah = max(n["high"] for n in va_nodes)
            val = min(n["low"] for n in va_nodes)

            # 4. Final Payload Assembly
            payload = {
                "metadata": {
                    "symbol": symbol.upper(),
                    "poc": round(poc_price, 2),
                    "vah": round(vah, 2),
                    "val": round(val, 2),
                    "total_volume": int(total_volume),
                    "va_percentage": 0.70,
                    "bin_count": len(nodes)
                },
                "nodes": nodes
            }
            
            return json.dumps(payload)

        except Exception as e:
            logger.error(f"Enhanced VP Error for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Error: Enhanced Volume Profile calculation failed - {str(e)}"

            profile = df.groupby("price_bin", observed=True)["volume"].sum().reset_index()
            profile.columns = ["price_range", "total_volume"]
            profile["price_range"] = profile["price_range"].astype(str)
            return profile.to_json(orient="records")


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
            if df.empty:
                return f"Error: No data for {symbol}"

            # Risk free rate from TNX geometry or fallback 4.28%
            rf = 0.0428
            try:
                tnx = _fetch_stock_history("^TNX", "1d", "1d")
                if not tnx.empty:
                    rf = tnx["Close"].iloc[-1] / 100.0
            except:
                pass

            df.columns = [str(c).lower() for c in df.columns]
            current_price = df["close"].iloc[-1]
            returns = df["close"].pct_change().dropna()

            if t_price and t_price > 0.0:
                # Projected Sharpe: S = (Target_Return - Rf) / Realized_Volatility
                target_return = (t_price - current_price) / current_price
                vol = returns.std()
                s = (target_return - rf) / (vol if vol > 0 else 0.0001)
                return f"### Projected Sharpe Ratio: {symbol.upper()}\n- Target Price: ${t_price:.2f}\n- Current: ${current_price:.2f}\n- Projected Return: {target_return * 100:.2f}%\n- Risk-Free (.TNX): {rf * 100:.2f}%\n- Volatility (20-day σ): {vol * 100:.2f}%\n- **Sharpe Ratio (S):** {s:.2f}"
            else:
                # Historical Annualized
                avg_return = returns.mean()
                vol = returns.std()
                daily_rf = rf / 252.0
                s_historical = ((avg_return - daily_rf) / vol) * np.sqrt(252)
                return f"### Historical Sharpe Ratio: {symbol.upper()}\n- Historical Volatility: {vol * 100:.2f}%\n- Risk-Free (.TNX): {rf * 100:.2f}%\n- **Historical Sharpe:** {s_historical:.2f}"

        except Exception as e:
            return f"Error computing Sharpe for {symbol}: {e}"

    return await asyncio.to_thread(compute, ticker, target_price, period, interval)


@tool
async def get_sortino_ratio(ticker: str, target_price: float = 0.0, period: str = "20d", interval: str = "1d", mode: str = "") -> str:
    """
    Primitive: Calculates the Sortino Ratio for a ticker using the 10Y Yield (.TNX) as the risk-free rate.
    If mode='day_trading', it uses a 0% MAR and high-frequency data for tactical assessment.
    Preferred over Sharpe as it only penalizes downside volatility.
    """

    def compute(symbol, t_price, p, i, m):
        try:
            if not m:
                m = os.getenv("VLI_TRADING_STYLE", "day_trading")
                
            # Use day trading defaults if specified
            if m == "day_trading":
                # Ensure we have enough data points for a meaningful ratio
                if p == "20d": p = "2d" 
                if i == "1d": i = "5m"
            
            df = _fetch_stock_history(symbol, p, i)
            if df.empty:
                return {"error": f"No data for {symbol}", "sortino": 0.0}

            # 1. Determine Risk-Free Rate (MAR)
            rf = 0.0
            if m != "day_trading":
                rf = 0.0428 # Fallback
                try:
                    tnx = _fetch_stock_history("^TNX", "1d", "1d")
                    if not tnx.empty:
                        rf = tnx["Close"].iloc[-1] / 100.0
                except: pass
            
            # 2. Daily/Period Normalization
            # For 1d interval, annualize by sqrt(252). 
            # For 5m interval, annualize by sqrt(19656) -- roughly (78 bars * 252 days)
            annualization_factor = np.sqrt(252)
            if i == "5m":
                annualization_factor = np.sqrt(78 * 252)
            elif i == "15m":
                annualization_factor = np.sqrt(26 * 252)

            df.columns = [str(c).lower() for c in df.columns]
            current_price = df["close"].iloc[-1]
            returns = df["close"].pct_change().dropna()
            
            # Periodic risk-free rate
            p_rf = rf / (252 if i == "1d" else (78 * 252 if i == "5m" else 1))
            
            downside_dev = calculate_downside_deviation(returns, p_rf)

            if t_price and t_price > 0.0:
                # Projected Sortino
                target_return = (t_price - current_price) / current_price
                s = (target_return - rf) / (downside_dev if downside_dev > 0 else 0.0001)
                report = f"### Projected Sortino Ratio: {symbol.upper()}\n- Target: ${t_price:.2f}\n- Projected Return: {target_return * 100:.2f}%\n- **Sortino (S_d):** {s:.2f}"
                return {"sortino": round(s, 2), "report": report}
            else:
                # Historical
                avg_return = returns.mean()
                s_historical = ((avg_return - p_rf) / downside_dev) * annualization_factor if downside_dev > 0 else 0
                
                label = "Day Trading" if m == "day_trading" else "Historical"
                report = f"### {label} Sortino Ratio: {symbol.upper()}\n- Downside Dev: {downside_dev * 100:.2f}%\n- **{label} Sortino:** {s_historical:.2f}"
                return {"sortino": round(s_historical, 2), "report": report}

        except Exception as e:
            logger.error(f"Sortino Error for {symbol}: {e}")
            return {"error": str(e), "sortino": 0.0}

    res = await asyncio.to_thread(compute, ticker, target_price, period, interval, mode)
    # ALWAYS return string for the tool infrastructure, but internal callers can json.loads
    return json.dumps(res)

