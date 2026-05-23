# Agent: Prose Writer - Node definition for text fixing.
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

from langchain_core.messages import HumanMessage, SystemMessage

from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type
from src.prompts.template import get_prompt_template
from src.prose.graph.state import ProseState
from src.tools.shared_storage import GLOBAL_CONTEXT, PROSE_CONTEXT

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS node.
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context: Persistent, shared across all Prose Writer nodes
_SHARED_RESOURCE_CONTEXT = PROSE_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


def prose_fix_node(state: ProseState):
    """Prose fix node implementation."""
    logger.info("Generating prose fix content.")
    model = get_llm_by_type(AGENT_LLM_MAP.get("prose_writer", "basic"))
    prose_content = model.invoke(
        [
            SystemMessage(content=get_prompt_template("prose/prose_fix")),
            HumanMessage(content=f"The existing text is: {state['content']}"),
        ],
    )
    logger.info(f"prose_content: {prose_content}")
    return {"output": prose_content.content}
