# Agent: Research - Core macro and data synthesis tools.
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

import asyncio
import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from src.services.macro_registry import macro_registry

from src.config.vli import get_vli_path
from .finance import _extract_ticker_data, _fetch_batch_history, get_symbol_history_data
from .shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT

NY_TZ = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context
_SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT

# 3. Global context
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


# Global cache for macro data
_MACRO_CACHE: dict[str, Any] = {"data": None, "timestamp": None}


# Registry-backed Macro Symbol Set
def get_macro_tickers():
    return macro_registry.get_macros()


# The following are maintained for legacy compatibility but now proxy to the registry
MACRO_TICKERS = get_macro_tickers()

MACRO_NAMES = {
    "VIX": "CBOE Volatility Index",
    "DXY": "US Dollar Index",
    "TNX": "10-Year Treasury Yield",
    "SPY": "S&P 500 Trust ETF",
    "QQQ": "Nasdaq 100 ETF",
    "IWM": "Russell 2000 ETF",
    "SI": "Silver Futures",
    "BTC": "Bitcoin (USD)",
    "USO": "United States Oil Fund",
    "WTI": "WTI Crude Oil",
}

TIMEFRAMES = ["1h", "1d"]


@tool
async def fetch_market_macros(structural: bool = True) -> str:
    """
    Fetch comprehensive market macro data for key global indices and assets.
    Utilizes the Ground Truth Macro Watchlist state for consistency with the dashboard.
    
    If structural=True (default), returns the high-fidelity JSON payload (Sortino, Sparklines).
    If structural=False, returns a legacy Markdown report.
    """
    from .finance import get_macro_symbols
    
    # [CONVERGENCE] Proxy to the hardened finance engine
    json_res = await get_macro_symbols.ainvoke({"fast_update": False})
    
    if structural:
        return json_res
        
    # Legacy Markdown Fallback
    import json
    try:
        data_obj = json.loads(json_res)
        headers = data_obj.get("headers", [])
        rows = data_obj.get("rows", [])
        
        report = "## [GROUND_TRUTH]: Macro Market Environment Report\n"
        report += f"Source: VLI Unified Engine | Sync Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
        
        for row in rows:
            # Row index mapping: Asset, Ticker, Price, Change%, Sortino, Trend
            label = row[0]
            ticker = row[1]
            price = row[2]
            change = row[3]["value"] if isinstance(row[3], dict) else row[3]
            sortino = row[4]
            
            report += f"### {label} ({ticker})\n"
            report += f"- **Current Price**: {price} ({change:+.2f}%)\n"
            report += f"- **Sortino Ratio**: {sortino:.2f}\n\n"
            
        return report
    except Exception as e:
        logger.error(f"Macro Proxy Error: {e}")
        return json_res # Fallback to raw JSON if parse fails



_LOOKBACK = 10
_INTERVAL = "1h"
_LOOKBACK = 10
_INTERVAL = "1h"


async def get_macro_data() -> list[dict[str, Any]]:
    """
    Structured version of market macros for API consumption.
    Refactored for speed:
    1. Bulk fetch quotes for all tickers.
    2. Parallelize SMC/Sortino tasks (throttled by the global finance lock).
    """
    logger.info(f"Fetching structured macro data (LB={_LOOKBACK}, INT={_INTERVAL})...")

    # Fetch from dynamic registry
    current_macros = macro_registry.get_macros()
    tickers = list(current_macros.values())
    labels = list(current_macros.keys())

    # 1. Bulk Fetch Quotes (15m for speed)
    history_report = await get_symbol_history_data.ainvoke({"symbols": tickers, "period": "1d", "interval": "15m"})

    # 2. Bulk Fetch Sparklines (last 5 days)
    sparkline_data = await asyncio.to_thread(_fetch_batch_history, tickers, "5d", _INTERVAL)

    # Parse prices from bulk report
    prices = {}
    for line in history_report.split("###"):
        if not line.strip():
            continue
        try:
            name_part = line.split("\n")[0].strip()
            close_match = re.search(r"Close\*\*:\s*([\d\.,]+)", line)
            if close_match:
                prices[name_part] = float(close_match.group(1).replace(",", ""))
        except Exception as e:
            logger.error(f"Error parsing price for part: {e}")

    async def process_one(label: str, yahoo_ticker: str):
        try:
            # Extract Sparkline and calculate % Change
            sparkline = []
            change_pct = 0.0
            try:
                ticker_spark_df = _extract_ticker_data(sparkline_data, yahoo_ticker)
                if not ticker_spark_df.empty:
                    # Calculate % change from start of period
                    start_price = float(ticker_spark_df.iloc[0]["Close"])
                    current_price = float(ticker_spark_df.iloc[-1]["Close"])
                    if start_price > 0:
                        change_pct = ((current_price - start_price) / start_price) * 100

                    # Take last _LOOKBACK non-null values for the UI charts
                    last_n = ticker_spark_df.tail(_LOOKBACK)
                    for _, row in last_n.iterrows():
                        ts = row.name
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=ZoneInfo("UTC"))

                        sparkline.append({"v": float(row["Close"]), "t": ts.astimezone(NY_TZ).strftime(" %m/%d  %I:%M %p").lower()})
            except Exception as e:
                logger.error(f"Sparkline error for {yahoo_ticker}: {e}")

            return {
                "label": label,
                "name": MACRO_NAMES.get(label, ""),
                "ticker": yahoo_ticker,
                "price": prices.get(yahoo_ticker, 0.0) or prices.get(yahoo_ticker.upper(), 0.0),
                "change": change_pct,
                "sortino": 0.0,
                "trends": {},
                "sparkline": sparkline,
            }
        except Exception as e:
            logger.error(f"Error {label}: {e}")
            return {"label": label, "name": MACRO_NAMES.get(label, ""), "ticker": yahoo_ticker, "price": 0.0, "change": 0.0, "sortino": 0.0, "trends": {}, "sparkline": []}

    # 3. Parallelize processing (Now extremely fast since no sub-tool calls are made)
    tasks = [process_one(l, t) for l, t in MACRO_TICKERS.items()]
    results = await asyncio.gather(*tasks)

    now = datetime.now()
    _MACRO_CACHE["data"] = results
    _MACRO_CACHE["timestamp"] = now
    return results


@tool
async def fetch_economic_calendar() -> str:
    """
    Scraper Primitive: Fetches the forward-looking Macro Economic Calendar for this week.
    Returns highly anticipated "Red Folder" macro events (like CPI, FOMC, Earnings)
    that will drive volatility and sentiment.
    """
    import requests
    import json
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    ny_tz = ZoneInfo("America/New_York")
    
    try:
        response = await asyncio.to_thread(requests.get, url, timeout=10)
        
        if response.status_code != 200:
            return f"Failed to fetch economic calendar. Status code: {response.status_code}"
            
        data = response.json()
        
        high_impact_events = []
        for event in data:
            # We strictly want High impact for systemic events 
            if event.get("impact") == "High":
                event_date_str = event.get("date", "")
                
                try:
                    dt = datetime.fromisoformat(event_date_str)
                    formatted_date = dt.astimezone(ny_tz).strftime("%A, %I:%M %p EST")
                except:
                    formatted_date = event_date_str
                
                title = event.get("title", "Unknown Event")
                country = event.get("country", "")
                forecast = event.get("forecast", "")
                previous = event.get("previous", "")
                
                info = f"- **{country}**: {title} | {formatted_date}"
                if forecast or previous:
                    info += f" (Forecast: {forecast}, Prev: {previous})"
                high_impact_events.append(info)
        
        if not high_impact_events:
            return "No high-impact 'Red Folder' events scheduled for this week."
            
        report = "## Forward-Looking Macro Calendar:\n"
        report += "\n".join(high_impact_events)
        return report
        
    except Exception as e:
        logger.error(f"Error fetching economic calendar: {e}")
        return f"[ERROR] Failed to fetch macroeconomic calendar: {e}"

