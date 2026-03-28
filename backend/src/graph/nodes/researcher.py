# Agent: Researcher - Node definition for high-level data synthesis.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

from src.config.configuration import Configuration
from src.tools import (
    get_web_search_tool, crawl_tool, get_stock_quote, get_symbol_history_data, fetch_market_macros,
    get_smc_analysis, get_ema_analysis, get_rsi_analysis, get_macd_analysis,
    get_volatility_atr, get_volume_profile, get_bollinger_bands, snapper, simulate_cache_volatility
)
from src.tools.research import RULES as RESEARCH_RULES
from src.tools.shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT
from ..types import State
from .common import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module. (Option 1 Isolation)
# Any attempt by other agents to access this will cause an error (NameError).
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by Analyst sub-modules (including Researcher specialization)
_SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

async def researcher_node(state: State, config: RunnableConfig):
    """Researcher node implementation."""
    logger.info("Researcher Node: Initializing.")
    
    # Example usage of private context (mimicking existing logic)
    if not _NODE_RESOURCE_CONTEXT.get("macro_history"):
        logger.info("Research Node: Initializing private macro history storage.")
        try:
            macro_data = await get_symbol_history_data.ainvoke({
                "symbols": RESEARCH_RULES["MACRO_SET"],
                "period": RESEARCH_RULES["DEFAULT_LOOKBACK"],
                "interval": RESEARCH_RULES["DEFAULT_INTERVAL"]
            })
            _NODE_RESOURCE_CONTEXT["macro_history"] = macro_data
        except Exception as e:
            logger.error(f"Failed to initialize Research macro history: {e}")

    configurable = Configuration.from_runnable_config(config)
    tools = [
        # Researcher extended tools
        get_web_search_tool(configurable.max_search_results), 
        crawl_tool,
        snapper,
        # Analyst base tools
        get_stock_quote, 
        fetch_market_macros,
        get_smc_analysis, 
        get_ema_analysis, 
        get_rsi_analysis, 
        get_macd_analysis,
        get_volatility_atr, 
        get_volume_profile, 
        get_bollinger_bands,
        simulate_cache_volatility
    ]

    return await _setup_and_execute_agent_step(state, config, "researcher", tools)
