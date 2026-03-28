# Agent: Analyst - Node definition for technical financial analysis.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

from src.tools import (
    get_smc_analysis, get_ema_analysis, get_stock_quote, get_rsi_analysis,
    get_macd_analysis, get_volatility_atr, get_volume_profile, get_bollinger_bands,
    fetch_market_macros
)
from src.tools.shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT
from ..types import State
from .common import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

async def analyst_node(state: State, config: RunnableConfig):
    """Analyst node implementation."""
    cached_list = ", ".join(sorted(list(GLOBAL_CONTEXT.get("cached_tickers", set()))))
    logger.info(f"Analyst Node: Synthesizing technical indicators. GLOBAL_CACHE_VISIBILITY=[{cached_list}]")
    tools = [
        get_smc_analysis, get_ema_analysis, get_stock_quote, get_rsi_analysis,
        get_macd_analysis, get_volatility_atr, get_volume_profile, get_bollinger_bands,
        fetch_market_macros
    ]

    instructions = f"Report verbosity={state.get('verbosity', 1)}. "
    return await _setup_and_execute_agent_step(state, config, "analyst", tools, agent_instructions=instructions)
