import asyncio
import os
import logging
from src.graph.builder import graph
from langchain_core.messages import HumanMessage

# Set up logging to console to see node traces
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vli_trace")

async def trace_oxy_loop():
    print("🚀 TRACING VLI GRAPH (User Thread) for 'What is the price of oxy'")
    
    workflow_config = {"configurable": {"thread_id": "vli-session-default"}, "recursion_limit": 100}
    workflow_input = {
        "messages": [HumanMessage(content="What is the price of oxy")],
        "is_test_mode": True
    }
    
    try:
        print("--- STARTING INVOCATION ---")
        final_state = await graph.ainvoke(workflow_input, config=workflow_config)
        print("--- FINISHED ---")
        print(f"LAST NODE: {final_state.get('last_node')}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(trace_oxy_loop())
