import asyncio
import os
import logging
from src.graph.builder import graph
from langchain_core.messages import HumanMessage

# Set up logging to console to see node traces
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vli_trace")

async def trace_oxy():
    print("🚀 TRACING VLI GRAPH for 'What is the price of oxy'")
    
    workflow_config = {"configurable": {"thread_id": "trace-thread-123"}, "recursion_limit": 100}
    workflow_input = {
        "messages": [HumanMessage(content="What is the price of oxy")],
        "is_test_mode": True
    }
    
    try:
        # Run step by step if possible, but let's just run it and see the logs
        print("--- STARTING INVOCATION ---")
        final_state = await graph.ainvoke(workflow_input, config=workflow_config)
        print("--- FINISHED ---")
        
        if "final_report" in final_state:
            print(f"RESULT: {final_state['final_report']}")
        else:
            print("No final report found.")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(trace_oxy())
