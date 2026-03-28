# Agent: Scout - Node definition for data retrieval and brokerage.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

from src.config.configuration import Configuration
from src.tools import (
    get_brokerage_accounts, get_brokerage_history, get_brokerage_balance,
    get_brokerage_statements, get_stock_quote, get_web_search_tool, crawl_tool, snapper, simulate_cache_volatility
)
from src.tools.shared_storage import SCOUT_CONTEXT, GLOBAL_CONTEXT
from ..types import State
from .common import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = SCOUT_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

async def scout_node(state: State, config: RunnableConfig):
    """Scout node implementation."""
    logger.info("Scout Node: Initializing.")
    
    # 1. Manually emit a Trace message if in Test Mode to ensure visibility in Dashboard
    if state.get("test_mode"):
        from langchain_core.messages import AIMessage
        state["messages"].append(AIMessage(
            content=f"🔍 Request received for data retrieval: {state.get('research_topic', 'Unknown')}",
            name="scout"
        ))

    configurable = Configuration.from_runnable_config(config)
    tools = [
        get_brokerage_accounts, 
        get_brokerage_history, 
        get_brokerage_balance, 
        get_brokerage_statements, 
        get_stock_quote,
        get_web_search_tool(configurable.max_search_results),
        crawl_tool,
        snapper,
        simulate_cache_volatility
    ]

    return await _setup_and_execute_agent_step(state, config, "scout", tools)
