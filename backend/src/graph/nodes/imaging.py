# Agent: Imaging - Node definition for chart and visual data generation.
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
from src.tools import get_image_from_local_path, get_image_from_url, get_stock_quote, get_web_search_tool, python_repl_tool, snapper
from src.tools.shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT

from ..types import State
from .common_vli import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

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
