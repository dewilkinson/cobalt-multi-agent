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

from collections import defaultdict
from typing import Literal

# Define available LLM types
LLMType = Literal["basic", "reasoning", "vision", "code", "core", "legacy"]

# 1. Base dictionary for explicit mappings
_BASE_AGENT_LLM_MAP: dict[str, LLMType] = {
    "coordinator": "reasoning",
    "parser": "basic",
    "planner": "basic",
    "synthesizer": "reasoning",
    "coder": "basic",
    "reporter": "reasoning",
    "podcast_script_writer": "basic",
    "ppt_composer": "basic",
    "prose_writer": "basic",
    "prompt_enhancer": "basic",
    "scout": "basic",
    "journaler": "basic",
    "portfolio_manager": "basic",
    "risk_manager": "basic",
    "analyst": "basic",
    "smc_analyst": "basic",
    "imaging": "vision",
    "vision_specialist": "vision",
    "system": "basic",
}

# 2. Resilient Registry: Never throws KeyError, defaults to "basic"
AGENT_LLM_MAP = defaultdict(lambda: "basic", _BASE_AGENT_LLM_MAP)
