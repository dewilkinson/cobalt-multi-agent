# Agent: Imaging - Node definition for chart and visual data generation.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

from src.config.configuration import Configuration
from src.tools import get_stock_quote, get_web_search_tool, python_repl_tool, get_image_from_url, get_image_from_local_path, snapper
from src.tools.shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT
from ..types import State
from .common import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type (Analyst/Imaging)
_SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

async def imaging_node(state: State, config: RunnableConfig):
    """Imaging node implementation."""
    logger.info("Imaging Node: Creating visual data.")
    configurable = Configuration.from_runnable_config(config)
    tools = [get_stock_quote, get_web_search_tool(configurable.max_search_results), python_repl_tool, get_image_from_url, get_image_from_local_path, snapper]

    return await _setup_and_execute_agent_step(state, config, "imaging", tools)
