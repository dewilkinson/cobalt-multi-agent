# Agent: Coordinator - Node definition for multi-step graph orchestration.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any, Literal
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

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

import os

def coordinator_node(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """Coordinator node - Detailed multi-step planning."""
    logger.info("VLI Coordinator is planning execution.")
    analyst_keywords = ", ".join(get_analyst_keywords())
    
    # [NEW] Inject Daily Action Plan into GLOBAL_CONTEXT
    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if vault_path:
        plan_file = os.path.join(vault_path, "_cobalt", "Daily_Action_Plan.md")
        if os.path.exists(plan_file):
            with open(plan_file, "r", encoding="utf-8") as f:
                GLOBAL_CONTEXT["daily_action_plan"] = f.read()
    
    # 1. Setup LLM and Tools
    llm = get_llm_by_type(AGENT_LLM_MAP.get("coordinator", "reasoning"))
    from .common_vli import get_orchestrator_tools
    tools = get_orchestrator_tools(config)
    llm_with_tools = llm.bind_tools(tools)
    structured_llm = llm_with_tools.with_structured_output(Plan)
    
    # 2. Check if we are returning from an agent (Turn Detection)
    current_plan = state.get("current_plan")
    steps_completed = state.get("steps_completed", 0)
    
    # NEW: More robust check for agent turn completion.
    # If the most recent message is an AIMessage with a name that isn't coordinator/parser, a step was likely finished.
    last_msgs = state["messages"][-3:] if state.get("messages") else []
    from_agent = False
    last_agent_name = None
    
    if last_msgs:
        last_msg = last_msgs[-1]
        msg_name = getattr(last_msg, "name", None)
        
        # If the message is explicitly named by one of our nodes
        if msg_name and msg_name not in ["coordinator", "vli_coordinator", "vli_parser", "assistant", "Assistant"]:
            from_agent = True
            last_agent_name = msg_name
            logger.info(f"[COORD] Detected turn completion from agent: {msg_name}")
    
    if from_agent and current_plan:
        steps_completed += 1
        logger.info(f"[COORD] Incremented completion to {steps_completed}/{len(current_plan.steps)} due to {last_agent_name}")
        if steps_completed >= len(current_plan.steps):
            return {
                "steps_completed": steps_completed,
                "messages": [AIMessage(content="Finalizing research session. Synthesizing results...", name="coordinator")]
            }
        return {"steps_completed": steps_completed}

    # 3. Apply Multi-Step Planning Template
    cached_tickers_set = set()
    try:
        global_tickers = GLOBAL_CONTEXT.get("cached_tickers", set())
        cached_tickers_set.update(global_tickers)
    except Exception as e:
        logger.debug(f"Could not read global ticker cache for coordinator: {e}")
        
    from src.config.configuration import Configuration
    configurable = Configuration.from_runnable_config(config)
    dev_mode = getattr(configurable, 'developer_mode', False)
    
    from src.services.macro_registry import macro_registry
    macro_labels = ", ".join(list(macro_registry.get_macros().keys()))
    
    state_for_prompt = {
        **state, 
        "DEVELOPER_MODE": str(dev_mode).lower(),
        "ANALYST_KEYWORDS": analyst_keywords,
        "MACRO_INDICATORS": macro_labels,
        "CACHED_TICKERS": ", ".join(sorted(list(cached_tickers_set))) if cached_tickers_set else "None (Data Store Empty)",
        "DAILY_ACTION_PLAN": GLOBAL_CONTEXT.get("daily_action_plan", "No daily instructions provided.")
    }
    
    messages = apply_prompt_template("coordinator", state_for_prompt)
    plan_obj = structured_llm.invoke(messages)
    
    # [CONTEXT POISONING GUARDRAIL]
    if (not plan_obj.steps or plan_obj.has_enough_context) and not state.get("direct_mode", False):
        tech_keywords = ["analyze", "analysis", "smc", "sortino", "sharpe", "report"]
        user_query_content = str(state.get("messages", [])).lower()
        if any(kw in user_query_content for kw in tech_keywords):
            logger.warning(f"[COORD] Guardrail triggered: Coordinator hallucinated direct response for technical query. Forcing smc_analyst step.")
            plan_obj.has_enough_context = False
            plan_obj.direct_response = ""
            from src.prompts.planner_model import Step, StepType
            user_context = state.get("messages", [])[-1].content if state.get("messages") else "the target ticker"
            plan_obj.steps = [
                Step(
                    need_search=False,
                    title="Forced Technical Execution",
                    description=f"Run deep structural analysis to gather empirical data for user request: {user_context}",
                    step_type=StepType.SMC_ANALYST
                )
            ]
    
    return {
        "current_plan": plan_obj,
        "steps_completed": steps_completed,
        "messages": [AIMessage(content=f"Plan formulated: {plan_obj.title}. Ready to execute {len(plan_obj.steps)} steps.", name="coordinator")]
    }
