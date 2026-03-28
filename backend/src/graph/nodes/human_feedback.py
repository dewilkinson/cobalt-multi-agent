# Core: Human Feedback - Node definition for user reviews and routing.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Literal, Dict, Any
from langchain_core.messages import HumanMessage
from langgraph.types import Command, interrupt
from src.prompts.planner_model import Plan
from src.tools.shared_storage import GLOBAL_CONTEXT
from ..types import State

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

def human_feedback_node(state: State) -> Command[Literal["parser", "reporter", "researcher", "coder", "scout", "journaler", "analyst", "imaging", "system", "__end__"]]:
    """Human Feedback node implementation."""
    current_plan = state.get("current_plan")
    auto_accepted_plan = state.get("auto_accepted_plan", False)
    
    # Handle both Pydantic Plan and serialized dict
    plan_obj = current_plan
    is_pydantic = isinstance(plan_obj, Plan)
    
    # Auto-accept in Test or Debug mode
    import os
    from src.config.loader import get_bool_env
    vli_test = os.getenv("VLI_TEST_MODE", "").lower() in ("true", "1", "yes")
    vli_debug = os.getenv("VLI_DEBUG_MODE", "").lower() in ("true", "1", "yes")
    
    if vli_test or vli_debug or get_bool_env("VLI_TEST_MODE", False) or get_bool_env("VLI_DEBUG_MODE", False):
        logger.info("Test/Debug mode enabled: Automatically approving request.")
        auto_accepted_plan = True

    if not auto_accepted_plan:
        feedback = interrupt("Please Review the Plan.")
        if feedback and str(feedback).upper().startswith("[EDIT_PLAN]"):
            return Command(update={"messages": [HumanMessage(content=feedback, name="vli_feedback")]}, goto="parser")
        elif feedback and str(feedback).upper().startswith("[ACCEPTED]"):
            logger.info("Plan accepted.")
        else:
            raise TypeError(f"Unsupported feedback type: {feedback}")

    # Determine next routing
    steps = []
    if is_pydantic:
        steps = getattr(plan_obj, "steps", [])
    elif isinstance(plan_obj, dict):
        steps = plan_obj.get("steps", [])

    if not steps:
        logger.info("[ROUTING] No steps found in plan. Transitioning to Reporter.")
        return Command(goto="reporter")
    
    # Find the first step that hasn't been executed yet
    next_step = None
    for step in steps:
        execution_res = getattr(step, "execution_res", None) if not isinstance(step, dict) else step.get("execution_res")
        if execution_res is None:
            next_step = step
            break
            
    if not next_step:
        logger.info("[ROUTING] All steps completed. Transitioning to Reporter.")
        return Command(goto="reporter")
    
    st_raw = getattr(next_step, "step_type", "reporter") if not isinstance(next_step, dict) else next_step.get("step_type", "reporter")
    st = str(st_raw).lower()

    logger.info(f"[ROUTING] Planning transition to Node: {st} (Step: {getattr(next_step, 'title', 'Untitled') if not isinstance(next_step, dict) else next_step.get('title')})")

    if st == "research": return Command(goto="researcher")
    if st == "processing": return Command(goto="coder")
    if st == "scout": return Command(goto="scout")
    if st == "journaler": return Command(goto="journaler")
    if st == "analyst": return Command(goto="analyst")
    if st == "imaging": return Command(goto="imaging")
    if st == "system": return Command(goto="system")
    
    return Command(goto="reporter")
