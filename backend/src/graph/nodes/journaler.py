# Agent: Journaler - Node definition for diary and trade logging.
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

from src.tools import get_daily_blotter, get_journal_folder, get_stock_quote, list_journal_entries, read_journal_entry, set_journal_folder, write_daily_journal, log_feedback, get_personal_risk_metrics, get_attribution_summary
from src.tools.smc import run_smc_analysis, get_raw_smc_tables
from src.tools.indicators import get_volume_profile, get_intraday_snapshot
from src.tools.shared_storage import GLOBAL_CONTEXT, JOURNALER_CONTEXT

from ..types import State
from .common_vli import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = JOURNALER_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


async def journaler_node(state: State, config: RunnableConfig):
    """Journaler node implementation."""
    logger.info("Journaler Node: Documenting vibes and trades. SMC Execution context provided.")
    tools = [write_daily_journal, list_journal_entries, read_journal_entry, get_journal_folder, set_journal_folder, get_daily_blotter, get_stock_quote, log_feedback, run_smc_analysis, get_raw_smc_tables, get_volume_profile, get_intraday_snapshot, get_personal_risk_metrics, get_attribution_summary]

    return await _setup_and_execute_agent_step(state, config, "journaler", tools)
