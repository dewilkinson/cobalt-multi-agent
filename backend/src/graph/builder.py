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

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.graph.nodes import (
    analyst_node,
    coder_node,
    human_feedback_node,
    imaging_node,
    journaler_node,
    portfolio_manager_node,
    reporter_node,
    synthesizer_node,
    risk_manager_node,
    session_monitor_node,
    smc_analyst_node,
    system_node,
    terminal_specialist_node,
    vli_node,
    vision_specialist_node,
)
from src.graph.types import State


def router_logic(
    state: State,
) -> Literal["portfolio_manager", "analyst", "risk_manager", "journaler", "synthesizer", "coder", "imaging", "system", "reporter", "human_feedback", "session_monitor", "vision_specialist", "terminal_specialist", "__end__"]:
    """Conditional router supporting both High Efficiency and High Control workflows."""
    plan = state.get("current_plan")

    if not plan or not plan.steps:
        return "__end__" if state.get("raw_data_mode") else "reporter"

    steps_completed = state.get("steps_completed", 0)

    # DEBUG LOGS
    last_msg = state["messages"][-1] if state.get("messages") else None
    last_name = getattr(last_msg, "name", "None") if last_msg else "NoMsg"
    print(f"[ROUTER] Step: {steps_completed}/{len(plan.steps)} | LastMsg: {last_name}")

    if steps_completed >= len(plan.steps):
        return "__end__" if state.get("raw_data_mode") else "reporter"

    next_step = plan.steps[steps_completed]

    print(f"[ROUTER] Step {steps_completed} of {len(plan.steps)}. Next: {next_step.step_type.value}")

    # High Efficiency Check: If in simulation/test mode or explicitly autonomous, bypass human
    if state.get("is_test_mode", False):
        return next_step.step_type.value  # step_type is an Enum (scout, analyst, etc)

    # Default to High Control: Go to human feedback for the first step
    if steps_completed == 0 and not state.get("is_plan_approved", False):
        return "human_feedback"

    return next_step.step_type.value


def _build_base_graph():
    """Build and return the hub-and-spoke state graph."""
    builder = StateGraph(State)

    # Nodes
    builder.add_node("vli", vli_node)  # Unified Spine
    builder.add_node("human_feedback", human_feedback_node)
    builder.add_node("portfolio_manager", portfolio_manager_node)
    builder.add_node("analyst", analyst_node)
    builder.add_node("risk_manager", risk_manager_node)
    builder.add_node("journaler", journaler_node)
    builder.add_node("synthesizer", synthesizer_node)
    builder.add_node("coder", coder_node)
    builder.add_node("imaging", imaging_node)
    builder.add_node("system", system_node)
    builder.add_node("reporter", reporter_node)
    builder.add_node("session_monitor", session_monitor_node)
    builder.add_node("vision_specialist", vision_specialist_node)
    builder.add_node("terminal_specialist", terminal_specialist_node)
    builder.add_node("smc_analyst", smc_analyst_node)

    # Workflow Edges
    # 1. Entry Point
    builder.add_edge(START, "vli")

    # 2. Specialist Return Loop
    # ALL execution agents loop back to VLI for next-step evaluation or plan maintenance
    agents = ["portfolio_manager", "analyst", "smc_analyst", "risk_manager", "journaler", "synthesizer", "coder", "imaging", "system", "session_monitor", "vision_specialist", "terminal_specialist"]

    for agent in agents:
        builder.add_edge(agent, "vli")

    # 3. Terminal Node
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
memory = MemorySaver()
graph = _build_base_graph().compile(checkpointer=memory)
graph.config = {"recursion_limit": 100}
