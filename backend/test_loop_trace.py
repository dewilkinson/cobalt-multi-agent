import asyncio
import os
import sys

from src.graph.builder import build_graph_with_memory
from langchain_core.messages import HumanMessage
from src.config.vli_context import vli_client_id

vli_client_id.set("test_trace_123")

async def run_trace():
    print("Building graph...")
    graph = build_graph_with_memory()
    
    config = {
        "configurable": {
            "thread_id": "test_trace_thread",
            "vli_llm_type": "core", # Fast tier for spine
        },
        "recursion_limit": 100
    }
    
    inputs = {
        "messages": [HumanMessage(content="analyze mrvl")],
        "raw_data_mode": False
    }
    
    print("Invoking graph...")
    try:
        # stream the steps so we can see what nodes are executing
        async for output in graph.astream(inputs, config=config, stream_mode="updates"):
            for node_name, state_update in output.items():
                print(f"\n[NODE COMPLETED] -> {node_name}")
                if "steps_completed" in state_update:
                    print(f"   Steps Completed: {state_update['steps_completed']}")
                if "intent" in state_update:
                    print(f"   Intent: {state_update['intent']}")
                plan = state_update.get("current_plan")
                if plan:
                    if hasattr(plan, 'steps'):
                         print(f"   Plan Steps: {len(plan.steps)}")
                    elif isinstance(plan, dict):
                         print(f"   Plan Steps: {len(plan.get('steps', []))}")
                msgs = state_update.get("messages", [])
                if msgs:
                    last_msg = msgs[-1]
                    name = getattr(last_msg, 'name', '') or last_msg.type.upper()
                    print(f"   Last Message Name: {name}")
    except Exception as e:
        print(f"\n[GRAPH CRASH]: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_trace())
