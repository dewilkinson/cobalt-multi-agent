# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

from typing import Literal
from collections import defaultdict

# Define available LLM types
LLMType = Literal["basic", "reasoning", "vision", "code"]

# 1. Base dictionary for explicit mappings
_BASE_AGENT_LLM_MAP: dict[str, LLMType] = {
    "coordinator": "reasoning",
    "parser": "reasoning",
    "planner": "reasoning",
    "researcher":"basic",
    "coder": "basic",
    "reporter": "basic",
    "podcast_script_writer": "basic",
    "ppt_composer": "basic",
    "prose_writer": "basic",
    "prompt_enhancer": "basic",
    "scout": "basic",
    "journaler": "basic",

    "portfolio_manager": "reasoning",
    "risk_manager": "reasoning",

    "analyst": "reasoning",
    "smc_analyst": "reasoning",
    "imaging": "vision",
    "vision_specialist": "vision",
    "system": "basic",
}

# 2. Resilient Registry: Never throws KeyError, defaults to "basic"
AGENT_LLM_MAP = defaultdict(lambda: "basic", _BASE_AGENT_LLM_MAP)
