# Agent: System - Administrative and diagnostic orchestration node.
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
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.config.configuration import Configuration
from src.tools import (
    clear_vli_diagnostic,
    crawl_tool,
    fetch_market_macros,
    get_bollinger_bands,
    get_brokerage_accounts,
    get_brokerage_balance,
    get_brokerage_statements,
    get_attribution_summary,
    get_daily_blotter,
    get_personal_risk_metrics,
    get_cache_heat_map,
    manage_scheduled_tasks,
    get_ema_analysis,
    get_image_from_local_path,
    get_image_from_url,
    get_macd_analysis,
    get_rsi_analysis,
    get_smc_analysis,
    get_stock_quote,
    get_volatility_atr,
    get_volume_profile,
    get_web_search_tool,
    python_repl_tool,
    simulate_cache_volatility,
    snapper,
    vli_cache_tick,
)
from src.tools.shared_storage import ANALYST_CONTEXT, CODER_CONTEXT, GLOBAL_CONTEXT, JOURNALER_CONTEXT, ORCHESTRATOR_CONTEXT, PPT_CONTEXT, PROSE_CONTEXT, SCOUT_CONTEXT

from ..types import State
from .common_vli import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# The System Node has unparalleled access to all execution contexts across the orchestration graph.
_SYSTEM_RESOURCE_CONTEXT: dict[str, Any] = {
    "global": GLOBAL_CONTEXT,
    "scout": SCOUT_CONTEXT,
    "analyst": ANALYST_CONTEXT,
    "journaler": JOURNALER_CONTEXT,
    "coder": CODER_CONTEXT,
    "orchestrator": ORCHESTRATOR_CONTEXT,
    "prose": PROSE_CONTEXT,
    "ppt": PPT_CONTEXT,
}


async def system_node(state: State, config: RunnableConfig):
    """System node implementation."""
    configurable = Configuration.from_runnable_config(config)

    # System has access to practically everything
    tools = [
        get_web_search_tool(configurable.max_search_results),
        crawl_tool,
        snapper,
        get_stock_quote,
        fetch_market_macros,
        get_smc_analysis,
        get_ema_analysis,
        get_rsi_analysis,
        get_macd_analysis,
        get_volatility_atr,
        get_volume_profile,
        get_bollinger_bands,
        simulate_cache_volatility,  # Still included as a general tool, but restricted by prompt for this test
        get_cache_heat_map,
        manage_scheduled_tasks,
        get_brokerage_accounts,
        get_brokerage_balance,
        get_brokerage_statements,
        get_attribution_summary,
        get_daily_blotter,
        get_personal_risk_metrics,
        python_repl_tool,
        get_image_from_url,
        get_image_from_local_path,
        vli_cache_tick,
        clear_vli_diagnostic,
    ]

    # Injecting ORCHESTRATOR_CONTEXT for state persistence across ticks if needed
    state["context"] = state.get("context", {})
    state["context"]["orchestrator"] = ORCHESTRATOR_CONTEXT

    return await _setup_and_execute_agent_step(state, config, "system", tools)
