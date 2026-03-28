# Agent: Coordinator - Node definition for multi-step graph orchestration.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any, Literal
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type
from src.prompts.planner_model import Plan
from src.prompts.template import apply_prompt_template
from src.config.analyst import get_analyst_keywords
from src.tools.shared_storage import ORCHESTRATOR_CONTEXT, GLOBAL_CONTEXT
from ..types import State

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = ORCHESTRATOR_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

def coordinator_node(state: State, config: RunnableConfig) -> Command[Literal["human_feedback", "reporter", "__end__"]]:
    """Coordinator node - Detailed multi-step planning."""
    logger.info("VLI Coordinator is planning execution.")
    analyst_keywords = ", ".join(get_analyst_keywords())
    
    # Extract cached tickers to make the Coordinator "Cache Aware"
    cached_tickers_set = set()
        
    # Check Global Ticker Tracker from Scout
    try:
        from src.tools.shared_storage import GLOBAL_CONTEXT
        global_tickers = GLOBAL_CONTEXT.get("cached_tickers", set())
        cached_tickers_set.update(global_tickers)
    except Exception as e:
        logger.debug(f"Could not read global ticker cache for coordinator: {e}")
        
    from src.config.configuration import Configuration
    configurable = Configuration.from_runnable_config(config)
    dev_mode = getattr(configurable, 'developer_mode', False)
    
    state_for_prompt = {
        **state, 
        "DEVELOPER_MODE": str(dev_mode).lower(),
        "ANALYST_KEYWORDS": analyst_keywords,
        "CACHED_TICKERS": ", ".join(sorted(list(cached_tickers_set))) if cached_tickers_set else "None (Data Store Empty)"
    }
    logger.info(f"[COORD_PLANNER] VLI Coordinator (DevMode: {dev_mode}) found CACHED_TICKERS: {state_for_prompt['CACHED_TICKERS']}")
    
    messages = apply_prompt_template("coordinator", state_for_prompt)
    
    llm = get_llm_by_type(AGENT_LLM_MAP.get("coordinator", "reasoning"))
    from .common import get_orchestrator_tools
    tools = get_orchestrator_tools(config)
    llm_with_tools = llm.bind_tools(tools)
    structured_llm = llm_with_tools.with_structured_output(Plan)
    
    plan_obj = structured_llm.invoke(messages)
    return Command(
        update={
            "current_plan": plan_obj,
            "messages": [AIMessage(content=str(plan_obj), name="vli_coordinator")]
        },
        goto="human_feedback",
    )
