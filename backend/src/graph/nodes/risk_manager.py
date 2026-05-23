# Agent: Risk Manager - Node definition for High-Frequency Governance Layer.
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

from src.tools import fetch_market_macros, get_journal_folder, get_smc_analysis, get_sortino_ratio, get_volatility_atr, get_volume_profile, python_repl_tool, read_journal_entry, write_daily_journal, get_personal_risk_metrics
from src.tools.shared_storage import GLOBAL_CONTEXT, RISK_MANAGER_CONTEXT

from ..types import State
from .common_vli import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = RISK_MANAGER_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


async def risk_manager_node(state: State, config: RunnableConfig):
    """Risk Manager node implementation for risk validation and circuit breaking."""
    logger.info("Risk Manager Node: Enforcing Apex 500 Operating Context constraints.")

    # Tools to evaluate Macro pivots and internal parameters
    tools = [
        fetch_market_macros,
        python_repl_tool,  # Used for math calculations if not natively calculated
        write_daily_journal,  # Used to interact with Obsidian memory (re-using journal alias)
        read_journal_entry,
        get_journal_folder,
        get_sortino_ratio,
        get_smc_analysis,
        get_volume_profile,
        get_personal_risk_metrics,
    ]

    # Enforce strict reporting rules
    instructions = f"Report verbosity={state.get('verbosity', 1)}. "

    return await _setup_and_execute_agent_step(state, config, "risk_manager", tools, agent_instructions=instructions)
