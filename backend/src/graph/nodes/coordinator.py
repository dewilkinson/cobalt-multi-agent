# Agent: Coordinator - Node definition for multi-step graph orchestration.
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
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from src.tools.shared_storage import GLOBAL_CONTEXT, ORCHESTRATOR_CONTEXT
from ..types import State

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = ORCHESTRATOR_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


async def coordinator_node(state: State, config: RunnableConfig) -> dict[str, Any]:
    """Coordinator node - Detailed multi-step planning."""
    import os
    from src.config.agents import AGENT_LLM_MAP
    from src.config.analyst import get_analyst_keywords
    from src.llms.llm import get_llm_by_type
    from src.prompts.planner_model import Plan
    from src.prompts.template import apply_prompt_template

    logger.info("VLI Coordinator is planning execution.")
    analyst_keywords = ", ".join([str(k) for k in get_analyst_keywords()])

    # [NEW] Inject Daily Action Plan into GLOBAL_CONTEXT
    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if vault_path:
        plan_file = os.path.join(vault_path, "_cobalt", "Daily_Action_Plan.md")
        if os.path.exists(plan_file):
            with open(plan_file, encoding="utf-8") as f:
                GLOBAL_CONTEXT["daily_action_plan"] = f.read()

    # 1. Setup LLM and Tools
    from .common_vli import get_orchestrator_tools, _run_node_with_tiered_fallback

    tools = get_orchestrator_tools(config)

    # 2. Check if we are returning from an agent (Turn Detection)
    current_plan = state.get("current_plan")
    steps_completed = state.get("steps_completed", 0)

    # NEW: More robust check for agent turn completion.
    last_msgs = state["messages"][-3:] if state.get("messages") else []
    from_agent = False
    last_agent_name = None

    if last_msgs:
        last_msg = last_msgs[-1]
        msg_name = getattr(last_msg, "name", None)

        if msg_name and msg_name not in ["coordinator", "vli_coordinator", "vli_parser", "assistant", "Assistant"]:
            from_agent = True
            last_agent_name = msg_name
            logger.info(f"[COORD] Detected turn completion from agent: {msg_name}")

    if from_agent and current_plan:
        steps_completed += 1
        logger.info(f"[COORD] Incremented completion to {steps_completed}/{len(current_plan.steps)} due to {last_agent_name}")
        if steps_completed >= len(current_plan.steps):
            logger.info("[COORD] Finalizing research session. Synthesizing results...")
            return {"steps_completed": steps_completed}
        return {"steps_completed": steps_completed}

    # 3. Apply Multi-Step Planning Template
    cached_tickers_set = set()
    try:
        global_tickers = GLOBAL_CONTEXT.get("cached_tickers", set())
        cached_tickers_set.update(global_tickers)
    except Exception as e:
        logger.debug(f"Could not read global ticker cache for coordinator: {e}")

    state_for_prompt = state.copy()
    state_for_prompt.update({
        "ANALYST_KEYWORDS": analyst_keywords,
        "MACRO_INDICATORS": ", ".join([str(k) for k in list(GLOBAL_CONTEXT.keys())]),
        "CACHED_TICKERS": ", ".join([str(t) for t in sorted(list(cached_tickers_set))]) if cached_tickers_set else "None (Data Store Empty)",
        "DAILY_ACTION_PLAN": GLOBAL_CONTEXT.get("daily_action_plan", "No daily instructions provided."),
        "metadata": {
            "analyst_keywords": analyst_keywords,
            "cached_tickers": [str(t) for t in list(cached_tickers_set)],
            "macro_labels": ", ".join([str(k) for k in list(GLOBAL_CONTEXT.keys())]),
        }
    })
    
    messages = apply_prompt_template("coordinator", state_for_prompt)
    
    # [RELIABILITY: FALLBACK] Execute with tiered fallback
    try:
        plan_obj, fb_msgs = await _run_node_with_tiered_fallback("coordinator", state, config, tools=tools, is_structured=True, structured_schema=Plan, messages=messages)
        if getattr(plan_obj, "name", None) == "system_fallback_error":
             return {"final_report": str(plan_obj.content), "messages": fb_msgs + [plan_obj], "steps_completed": 999}
    except Exception as e:
        logger.error(f"[COORD] Structural Parsing Failure: {e}. Falling back to default analyst plan.")
        fb_msgs = []
        from src.prompts.planner_model import Step, StepType
        plan_obj = Plan(
            locale="en-US",
            has_enough_context=False,
            thought=f"Structural Failure Recovery: {str(e)[:100]}",
            title="Institutional Audit (Recovery)",
            steps=[Step(need_search=False, title="Technical Recovery Analysis", description="Perform core analysis", step_type=StepType.ANALYST)],
        )

    # [CONTEXT POISONING GUARDRAIL]
    user_query_content = ""
    if state.get("messages"):
        last_msg = state["messages"][-1]
        user_query_content = str(getattr(last_msg, "content", "")).lower()
    
    # 1. Unconditional Trade Analysis Intercept
    trade_intent_keywords = ["analyze", "show", "get", "print", "log", "review", "evaluate", "post-mortem", "postmortem", "summary"]
    trade_target_keywords = ["trades", "journal", "blotter", "executions", "today's action"]
    
    has_intent = any(kw in user_query_content for kw in trade_intent_keywords)
    has_target = any(kw in user_query_content for kw in trade_target_keywords)
    
    if has_intent and has_target:
        logger.warning("[COORD] Guardrail: Forced Journaler step for trade analysis.")
        plan_obj.has_enough_context = False
        plan_obj.direct_response = ""
        import re
        days_back = 2
        if "week" in user_query_content:
            days_back = 7
        elif "month" in user_query_content:
            days_back = 30
        elif "year" in user_query_content:
            days_back = 365
            
        days_match = re.search(r'(\d+)\s*days?', user_query_content)
        if days_match:
            days_back = int(days_match.group(1))
            
        from src.prompts.planner_model import Step, StepType
        desc = f"Analyze the user's execution efficiency for the past {days_back} days using the blotter. Use days_back={days_back}."
        plan_obj.steps = [Step(need_search=False, title="Trade Efficiency Analysis", description=desc, step_type=StepType.JOURNALER)]
        
    # 2. Conditional Technical Guardrail (Only if LLM tries to skip steps)
    elif (not plan_obj.steps or plan_obj.has_enough_context) and not state.get("direct_mode", False):
        tech_keywords = ["analyze", "analysis", "smc", "sortino", "sharpe", "report", "scan", "scanner", "watchlist"]
        if any(kw in user_query_content for kw in tech_keywords):
            logger.warning("[COORD] Guardrail triggered: Coordinator hallucinated direct response for technical query. Forcing smc_analyst step.")
            plan_obj.has_enough_context = False
            plan_obj.direct_response = ""
            from src.prompts.planner_model import Step, StepType

            user_context = state.get("messages", [])[-1].content if state.get("messages") else "the target ticker"
            plan_obj.steps = [Step(need_search=False, title="Forced Technical Execution", description=f"Run deep structural analysis for: {user_context}", step_type=StepType.SMC_ANALYST)]

    logger.info(f"[COORD] Plan formulated: {plan_obj.title}. Ready to execute {len(plan_obj.steps)} steps.")
    return {"current_plan": plan_obj, "steps_completed": steps_completed, "messages": fb_msgs}
