# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

from typing import Optional
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.prompts.planner_model import Plan, Step, StepType
from .nodes import (
    parser_node,
    coordinator_node,
    human_feedback_node,
    researcher_node,
    coder_node,
    scout_node,
    journaler_node,

    analyst_node,
    imaging_node,
    reporter_node,
    system_node,
    sentinel_rm_node
)
from .types import State

def _build_base_graph():
    """Build and return the base state graph with all VLI nodes and edges."""
    builder = StateGraph(State)
    
    # Entrance
    builder.add_edge(START, "parser")
    builder.add_node("parser", parser_node)
    
    # Core Planning
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("human_feedback", human_feedback_node)
    
    # Execution Agents
    builder.add_node("researcher", researcher_node)
    builder.add_node("coder", coder_node)
    builder.add_node("scout", scout_node)
    builder.add_node("journaler", journaler_node)

    builder.add_node("analyst", analyst_node)
    builder.add_node("sentinel_rm", sentinel_rm_node)
    builder.add_node("imaging", imaging_node)
    builder.add_node("system", system_node)
    
    # Synthesis
    builder.add_node("reporter", reporter_node)
    
    # Routing (Simplified for now - humans can edit these in nodes.py Command)
    builder.add_edge("parser", "coordinator") # Fallback if not direct
    builder.add_edge("coordinator", "human_feedback")
    
    # Execution to Reporter
    builder.add_edge("researcher", "reporter")
    builder.add_edge("coder", "reporter")
    
    # Scout acts as Data Broker -> Routes to Sentinel RM for High-Frequency Grading
    builder.add_edge("scout", "sentinel_rm")
    # Sentinel RM evaluates and mandates back to the Coordinator (Option B)
    builder.add_edge("sentinel_rm", "coordinator")
    
    builder.add_edge("journaler", "reporter")

    builder.add_edge("analyst", "reporter")
    builder.add_edge("imaging", "reporter")
    builder.add_edge("system", "reporter")
    
    builder.add_edge("reporter", END)
    
    return builder

def build_graph_with_memory():
    memory = MemorySaver()
    builder = _build_base_graph()
    return builder.compile(checkpointer=memory)

def build_graph():
    builder = _build_base_graph()
    return builder.compile()

graph = build_graph()
