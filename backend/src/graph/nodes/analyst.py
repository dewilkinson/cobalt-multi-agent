# Agent: Analyst - Node definition for technical financial analysis.
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

import logging
import asyncio
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.tools import fetch_market_macros, get_bollinger_bands, get_ema_analysis, get_macd_analysis, get_rsi_analysis, run_smc_analysis, get_batch_smc_analysis, get_stock_quote, get_volatility_atr, get_volume_profile, invalidate_market_cache, get_sortino_ratio
from src.tools.news import get_ticker_news
from src.tools.scanner import build_session_watchlist, run_activity_pulse, run_sensor_scope, clear_scanner_cache
from src.tools.shield_scanner_trawl import run_shield_trawl
from src.tools.artifacts import read_session_artifact
from src.tools.shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT

from ..types import State
from .common_vli import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


async def analyst_node(state: State, config: RunnableConfig):
    """Analyst node implementation."""
    cached_list = ", ".join([str(t) for t in sorted(list(GLOBAL_CONTEXT.get("cached_tickers", set())))])
    logger.info(f"Analyst Node: Synthesizing technical indicators. GLOBAL_CACHE_VISIBILITY=[{cached_list}]")

    # [PERFORMANCE] Proactive Pre-warming
    # Fetch 30-day history immediately to ensure the Analyst has warm data for sentiment performance summaries.
    try:
        from src.tools.finance import _fetch_stock_history, _normalize_ticker
        import re
        last_msg = state.get("messages", [])[-1].content if state.get("messages") else ""
        
        # [HARDENING] Extract all potential tickers and filter out commands/stop words
        potential_tickers = re.findall(r'\b[A-Z]{1,5}\b', str(last_msg))
        stop_words = {"GET", "FOR", "NEWS", "THE", "PRICE", "STOCK", "AND", "WITH", "DATA", "SMC", "CHART", "REPORT"}
        
        ticker = next((t for t in potential_tickers if t not in stop_words), None)
        
        if ticker:
            norm_t = _normalize_ticker(ticker)
            logger.info(f"[PRE-WARM] Proactively fetching 30d history for {norm_t}...")
            # Fetch common windows into shared Datastore/history_cache
            await asyncio.gather(
                asyncio.wait_for(asyncio.to_thread(_fetch_stock_history, norm_t, "30d", "1d"), timeout=15.0),
                asyncio.wait_for(asyncio.to_thread(_fetch_stock_history, norm_t, "5d", "1h"), timeout=10.0),
                return_exceptions=True
            )
    except Exception as e:
        logger.warning(f"[PRE-WARM] Analyst node pre-warm skipped/failed: {e}")

    tools = [run_smc_analysis, get_batch_smc_analysis, get_ema_analysis, get_stock_quote, get_rsi_analysis, get_macd_analysis, get_volatility_atr, get_volume_profile, get_bollinger_bands, fetch_market_macros, invalidate_market_cache, read_session_artifact, build_session_watchlist, run_activity_pulse, run_sensor_scope, clear_scanner_cache, run_shield_trawl, get_sortino_ratio, get_ticker_news]

    instructions = f"Report verbosity={state.get('verbosity', 1)}. "
    return await _setup_and_execute_agent_step(state, config, "analyst", tools, agent_instructions=instructions)
