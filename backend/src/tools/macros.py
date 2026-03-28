# Agent: Research - Core macro and data synthesis tools.
# Cobalt Multiagent - High-fidelity financial analysis platform

# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
import asyncio
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from .finance import get_symbol_history_data, get_sortino_ratio, _fetch_batch_history, _extract_ticker_data
from .smc import get_smc_analysis

from .shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT

NY_TZ = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context
_SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT

# 3. Global context
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


# Global cache for macro data
_MACRO_CACHE: Dict[str, Any] = {
    "data": None,
    "timestamp": None
}

# Define the standard macro set
MACRO_TICKERS = {
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",
    "TNX": "^TNX",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "IWM": "IWM",
    "GLD": "GLD",
    "BTC": "BTC-USD",
    "USO": "USO"
}

MACRO_NAMES = {
    "VIX": "CBOE Volatility Index",
    "DXY": "US Dollar Index",
    "TNX": "10-Year Treasury Yield",
    "SPY": "S&P 500 Trust ETF",
    "QQQ": "Nasdaq 100 ETF",
    "IWM": "Russell 2000 ETF",
    "GLD": "SPDR Gold ETF",
    "BTC": "Bitcoin (USD)",
    "USO": "United States Oil Fund"
}

TIMEFRAMES = ["15m", "1h", "4h", "1d"]

@tool
async def fetch_market_macros() -> str:
    """
    Fetch comprehensive market macro data for key global indices and assets.
    Provides price, trend, and stability (SMC/Sortino) analysis for major indices.
    """
    data = await get_macro_data()
    if not data:
        return "Error: Unable to synthesize macro market data at this time."
    
    report = "## Market Macros - High Fidelity Stock Analysis\n\n"
    
    for item in data:
        trends = item.get("trends", {})
        ts_str = ", ".join([f"{tf}: {trend}" for tf, trend in trends.items()])
        
        report += f"### {item['label']} ({item['name']})\n"
        report += f"- **Price**: {item['price']:.2f}\n"
        report += f"- **Sortino Ratio**: {item['sortino']:.2f}\n"
        report += f"- **SMC Trends**: {ts_str}\n\n"
        
    return report


_LOOKBACK = 10
_INTERVAL = "1h"
_LOOKBACK = 10
_INTERVAL = "1h"

async def get_macro_data() -> List[Dict[str, Any]]:
    """
    Structured version of market macros for API consumption.
    Refactored for speed:
    1. Bulk fetch quotes for all tickers.
    2. Parallelize SMC/Sortino tasks (throttled by the global finance lock).
    """
    logger.info(f"Fetching structured macro data (LB={_LOOKBACK}, INT={_INTERVAL})...")

    tickers = list(MACRO_TICKERS.values())
    labels = list(MACRO_TICKERS.keys())

    # 1. Bulk Fetch Quotes (1m for precision)
    history_report = await get_symbol_history_data.ainvoke({
        "symbols": tickers,
        "period": "1d",
        "interval": "1m"
    })

    # 2. Bulk Fetch Sparklines (last 10 of 1h interval)
    sparkline_data = await asyncio.to_thread(_fetch_batch_history, tickers, "15d", _INTERVAL)

    # Parse prices from bulk report
    prices = {}
    for line in history_report.split("###"):
        if not line.strip(): continue
        try:
            name_part = line.split("\n")[0].strip()
            close_match = re.search(r"Close\*\*:\s*([\d\.,]+)", line)
            if close_match:
                prices[name_part] = float(close_match.group(1).replace(',', ''))
        except Exception as e:
            logger.error(f"Error parsing price for part: {e}")

    async def process_one(label: str, yahoo_ticker: str):
        try:
            # Sortino Ratio (Throttled by lock)
            sortino_md = await get_sortino_ratio.ainvoke({"ticker": yahoo_ticker, "period": "3mo"})
            sortino = 0.0
            s_match = re.search(r"Value:\*\*\s*([\+\-\d\.,]+)", str(sortino_md))
            if s_match:
                try: sortino = float(s_match.group(1).replace(',', ''))
                except: pass

            # SMC (Throttled by lock)
            tf_trends = {tf: "Neutral" for tf in TIMEFRAMES}
            for tf in TIMEFRAMES:
                res = await get_smc_analysis.ainvoke({"ticker": yahoo_ticker, "period": "60d", "interval": tf})
                tf_data = str(res)
                if "Bullish" in tf_data: tf_trends[tf] = "Bullish"
                elif "Bearish" in tf_data: tf_trends[tf] = "Bearish"

            # Extract Sparkline with timestamps
            sparkline = []
            try:
                ticker_spark_df = _extract_ticker_data(sparkline_data, yahoo_ticker)
                if not ticker_spark_df.empty:
                    # Take last _LOOKBACK non-null values
                    last_n = ticker_spark_df.tail(_LOOKBACK)
                    sparkline = []
                    for _, row in last_n.iterrows():
                        # yfinance usually returns UTC for most intervals, handle naive as UTC
                        ts = row.name
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=ZoneInfo("UTC"))
                        
                        sparkline.append({
                            "v": float(row['Close']),
                            "t": ts.astimezone(NY_TZ).strftime(' %m/%d  %I:%M %p').lower()
                        })
            except Exception as e:
                logger.error(f"Sparkline error for {yahoo_ticker}: {e}")

            return {
                "label": label,
                "name": MACRO_NAMES.get(label, ""),
                "ticker": yahoo_ticker,
                "price": prices.get(yahoo_ticker, 0.0) or prices.get(yahoo_ticker.upper(), 0.0),
                "change": 0.0,
                "sortino": sortino,
                "trends": tf_trends,
                "sparkline": sparkline
            }
        except Exception as e:
            logger.error(f"Error {label}: {e}")
            return {
                "label": label, 
                "name": MACRO_NAMES.get(label, ""), 
                "ticker": yahoo_ticker, 
                "price": 0.0, 
                "change": 0.0, 
                "sortino": 0.0, 
                "trends": {},
                "sparkline": []
            }

    # 2. Parallelize processing (Lock in finance.py will handle the safety)
    tasks = [process_one(l, t) for l, t in MACRO_TICKERS.items()]
    results = await asyncio.gather(*tasks)
    
    _MACRO_API_CACHE["data"] = results
    _MACRO_API_CACHE["timestamp"] = now
    return results
