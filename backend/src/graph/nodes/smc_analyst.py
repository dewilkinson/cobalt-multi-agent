# Agent: SMC Analyst - Node definition for ICT-based market structure analysis.
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
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.tools.finance import get_stock_quote
from src.tools.news import get_ticker_news
from src.tools.smc import get_raw_smc_tables, run_smc_analysis
from src.tools.artifacts import read_session_artifact
from src.tools.indicators import get_sharpe_ratio, get_sortino_ratio, get_volatility_atr, get_volume_profile
from src.tools.scanner import trigger_morning_scan, trigger_manual_analysis_scan, clear_scanner_cache, build_session_watchlist, run_activity_pulse, run_sensor_scope
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


async def smc_analyst_node(state: State, config: RunnableConfig):
    """
    SMC Analyst node implementation.
    Specializes in Inner Circle Trader (ICT) concepts: FVG, Order Blocks, BOS, ChoCh.
    """
    cached_list = ", ".join([str(t) for t in sorted(list(GLOBAL_CONTEXT.get("cached_tickers", set())))])
    logger.info(f"SMC Analyst Node: Executing ICT Structural Analysis. GLOBAL_CACHE_VISIBILITY=[{cached_list}]")

    tools = [run_smc_analysis, get_raw_smc_tables, get_stock_quote, get_volume_profile, get_volatility_atr, get_sortino_ratio, get_sharpe_ratio, read_session_artifact, trigger_morning_scan, trigger_manual_analysis_scan, clear_scanner_cache, build_session_watchlist, run_activity_pulse, run_sensor_scope, get_ticker_news]

    # [PERFORMANCE] Node-level Pre-warming
    # Fetch all common data windows concurrently before starting the LLM to ensure tool hits are instant.
    try:
        from src.tools.finance import _fetch_stock_history, _normalize_ticker
        import re

        # Simple heuristic to find ticker in last message
        last_msg = state.get("messages", [])[-1].content if state.get("messages") else ""
        ticker_match = re.search(r'\b[A-Z]{1,5}\b', str(last_msg))
        if ticker_match:
            ticker = ticker_match.group(0)
            norm_t = _normalize_ticker(ticker)
            logger.info(f"[PRE-WARM] Proactively fetching institutional data for {norm_t}...")
            # Fire-and-forget concurrent fetches into the shared cache
            # We fetch the exact periods tools will soon request
            await asyncio.gather(
                asyncio.wait_for(asyncio.to_thread(_fetch_stock_history, norm_t, "60d", "1d"), timeout=10.0), # ATR/Quote
                asyncio.wait_for(asyncio.to_thread(_fetch_stock_history, norm_t, "20d", "1d"), timeout=10.0), # Sortino/Sharpe
                asyncio.wait_for(asyncio.to_thread(_fetch_stock_history, norm_t, "1mo", "1h"), timeout=10.0), # MTF Tactical
                asyncio.wait_for(asyncio.to_thread(_fetch_stock_history, norm_t, "5d", "5m"), timeout=10.0),  # MTF Trigger
                return_exceptions=True
            )
    except Exception as e:
        logger.warning(f"[PRE-WARM] Skipped/Failed: {e}")

    instructions = (
        "You are a specialized SMC (Smart Money Concepts) and ICT Analyst. "
        "Your goal is to identify institutional market structure. "
        "Always use the 'run_smc_analysis' tool for deep structural data (BOS, ChoCh, FVG, OB). "
        "If 'raw_data_mode' is True or explicitly requested in the prompt, prioritize 'get_raw_smc_tables' and return its JSON output exactly as received without synthesis. "
        "Explain these concepts to the user in a high-fidelity, institutional tone unless raw data is requested. "
        "Focus on 'Change of Character' (ChoCh) as a trend-reversal signal and 'Break of Structure' (BOS) as continuation. "
        "Report all identified FVG and Order Blocks as zones of interest. "
        "NOTE: Sortino ratio is the preferred ratio unless Sharpe is explicitly requested. "
        "Do not hallucinate outputs. If a tool fails with an error, gracefully relay the failure."
    )

    return await _setup_and_execute_agent_step(state, config, "smc_analyst", tools, agent_instructions=instructions)
