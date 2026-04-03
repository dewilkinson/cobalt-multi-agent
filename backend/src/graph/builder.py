# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

from typing import Optional, Literal, Dict, Any
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.prompts.planner_model import Plan, Step, StepType
from .nodes import (
    parser_node,
    coordinator_node,
    human_feedback_node,
    scout_node,
    portfolio_manager_node,
    analyst_node,
    risk_manager_node,
    journaler_node,
    researcher_node,
    coder_node,
    imaging_node,
    system_node,
    reporter_node,
    session_monitor_node,
    vision_specialist_node,
    terminal_specialist_node,
    smc_analyst_node
)
from .types import State

def router_logic(state: State) -> Literal["scout", "portfolio_manager", "analyst", "risk_manager", "journaler", "researcher", "coder", "imaging", "system", "reporter", "human_feedback", "session_monitor", "vision_specialist", "terminal_specialist"]:
    """Conditional router supporting both High Efficiency and High Control workflows."""
    plan = state.get("current_plan")
    
    if not plan or not plan.steps:
        return "reporter"
    
    steps_completed = state.get("steps_completed", 0)
    
    # DEBUG LOGS
    last_msg = state["messages"][-1] if state.get("messages") else None
    last_name = getattr(last_msg, "name", "None") if last_msg else "NoMsg"
    print(f"[ROUTER] Step: {steps_completed}/{len(plan.steps)} | LastMsg: {last_name}")

    if steps_completed >= len(plan.steps):
        return "reporter"
        
    next_step = plan.steps[steps_completed]
    
    print(f"[ROUTER] Step {steps_completed} of {len(plan.steps)}. Next: {next_step.step_type.value}")

    # High Efficiency Check: If in simulation/test mode or explicitly autonomous, bypass human
    if state.get("is_test_mode", False):
        return next_step.step_type.value # step_type is an Enum (scout, analyst, etc)

    # Default to High Control: Go to human feedback for the first step
    if steps_completed == 0 and not state.get("is_plan_approved", False):
         return "human_feedback"
         
    return next_step.step_type.value

def parser_router(state: State) -> Literal["coordinator", "reporter"]:
    """Determines if the Parser's Fast-Path was enough or if we need a Coordinator."""
    if state.get("final_report"):
        return "reporter"
    return "coordinator"

def _build_base_graph():
    """Build and return the hub-and-spoke state graph."""
    builder = StateGraph(State)
    
    # Nodes
    builder.add_node("parser", parser_node)
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("human_feedback", human_feedback_node)
    builder.add_node("scout", scout_node)
    builder.add_node("portfolio_manager", portfolio_manager_node)
    builder.add_node("analyst", analyst_node)
    builder.add_node("risk_manager", risk_manager_node)
    builder.add_node("journaler", journaler_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("coder", coder_node)
    builder.add_node("imaging", imaging_node)
    builder.add_node("system", system_node)
    builder.add_node("reporter", reporter_node)
    builder.add_node("session_monitor", session_monitor_node)
    builder.add_node("vision_specialist", vision_specialist_node)
    builder.add_node("terminal_specialist", terminal_specialist_node)
    builder.add_node("smc_analyst", smc_analyst_node)
    
    # Workflow Edges
    builder.add_edge(START, "parser")
    # REPLACE STATIC EDGE WITH DYNAMIC ROUTER
    builder.add_conditional_edges("parser", parser_router)
    
    # The Coordinator sends state to the Router
    builder.add_conditional_edges(
        "coordinator",
        router_logic,
        {
            "scout": "scout",
            "portfolio_manager": "portfolio_manager",
            "smc_analyst": "smc_analyst",
            "analyst": "analyst",
            "risk_manager": "risk_manager",
            "journaler": "journaler",
            "researcher": "researcher",
            "coder": "coder",
            "imaging": "imaging",
            "system": "system",
            "reporter": "reporter",
            "human_feedback": "human_feedback",
            "session_monitor": "session_monitor",
            "vision_specialist": "vision_specialist",
            "terminal_specialist": "terminal_specialist"
        }
    )
    
    # After human approval, we always go back to the coordinator to resume execution
    builder.add_edge("human_feedback", "coordinator")
    
    # ALL execution agents loop back to the coordinator for next-step evaluation
    # This maintains the Hub-and-Spoke integrity
    for agent in ["scout", "portfolio_manager", "analyst", "smc_analyst", "risk_manager", "journaler", "researcher", "coder", "imaging", "system", "session_monitor", "vision_specialist", "terminal_specialist"]:
        builder.add_edge(agent, "coordinator")
        
    builder.add_edge("reporter", END)
    
    return builder

def build_graph_with_memory():
    memory = MemorySaver()
    builder = _build_base_graph()
    return builder.compile(checkpointer=memory)

def build_graph():
    builder = _build_base_graph()
    return builder.compile()

# Global graph instance with high recursion and memory for checking state
from langgraph.checkpoint.memory import MemorySaver
memory = MemorySaver()
graph = _build_base_graph().compile(checkpointer=memory)
graph.config = {"recursion_limit": 100}
