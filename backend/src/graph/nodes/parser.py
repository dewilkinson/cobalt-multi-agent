# Agent: Parser - Node definition for initial vibe processing.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any, Literal
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.config.agents import AGENT_LLM_MAP
from src.config.configuration import Configuration
from src.llms.llm import get_llm_by_type
from src.prompts.planner_model import Plan
from src.prompts.template import apply_prompt_template
from src.tools.shared_storage import ORCHESTRATOR_CONTEXT, GLOBAL_CONTEXT
from ..types import State

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = ORCHESTRATOR_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

async def parser_node(state: State, config: RunnableConfig) -> Command[Literal["coordinator", "reporter", "__end__"]]:
    """Parser node (VibeLink Interface) - Initial Input Processor."""
    logger.info("VLI Parser is processing user vibe.")
    
    configurable = Configuration.from_runnable_config(config)
    from .common import get_orchestrator_tools
    tools = get_orchestrator_tools(config)
    
    llm = get_llm_by_type(AGENT_LLM_MAP.get("parser", "basic"))
    # Bind tools for potential bypass
    llm_with_tools = llm.bind_tools(tools)
    structured_llm = llm_with_tools.with_structured_output(Plan)

    messages = apply_prompt_template("parser", state)
    
    response = structured_llm.invoke(messages)
    plan_obj = response
    
    if plan_obj.has_enough_context or plan_obj.direct_response:
        return Command(
            update={
                "current_plan": plan_obj,
                "locale": plan_obj.locale,
                "final_report": plan_obj.direct_response or "",
                "messages": [AIMessage(content=str(plan_obj), name="vli_parser")]
            },
            goto="reporter",
        )
    return Command(
        update={
            "current_plan": plan_obj,
            "locale": plan_obj.locale,
            "research_topic": plan_obj.title,
        },
        goto="coordinator",
    )
