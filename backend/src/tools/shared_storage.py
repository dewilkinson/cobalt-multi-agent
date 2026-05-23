# Agent: Scout - Shared agent resource contexts for persistence.
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

from typing import Any
from collections import OrderedDict

# Centralized Agent Contexts (Durable during node execution)
# Each agent node has only one context shared by all sub-modules
# These are initialized when the agent spins up and should be cleared on termination if needed.

SCOUT_CONTEXT: dict[str, Any] = {}
ANALYST_CONTEXT: dict[str, Any] = {}
JOURNALER_CONTEXT: dict[str, Any] = {}
CODER_CONTEXT: dict[str, Any] = {}
RISK_MANAGER_CONTEXT: dict[str, Any] = {}
PORTFOLIO_MANAGER_CONTEXT: dict[str, Any] = {}
ORCHESTRATOR_CONTEXT: dict[str, Any] = {}
PROSE_CONTEXT: dict[str, Any] = {}
PPT_CONTEXT: dict[str, Any] = {}

# Global Shared Context (Visible to all agents of any type)
GLOBAL_CONTEXT: dict[str, Any] = {}
GENERAL_CONTEXT = GLOBAL_CONTEXT  # Alias for compatibility

# Persisted Market Data Cache (Used by Hybrid Resolver)
# Now using OrderedDict to support LRU eviction logic
history_cache: OrderedDict[str, Any] = OrderedDict()

# DataFrame Raw Price Caches
df_cache: OrderedDict[str, Any] = OrderedDict()

# Computed SMC Pre-Calculated Results
analysis_cache: OrderedDict[str, Any] = OrderedDict()
