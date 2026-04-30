import asyncio
import logging
import os
import sys

# Ensure backend/src is in PYTHONPATH
sys.path.append('c:/github/cobalt-multi-agent/backend')

from src.graph.builder import build_graph
from src.config.configuration import Configuration, get_recursion_limit
from src.config.agents import AGENT_LLM_MAP

# Configure logging
logging.basicConfig(level=logging.WARNING)

async def main():
    user_input = "/cma are the APA 1d 4h 1h multi timeframe trends consistent"
    print(f"Executing: {user_input}\n")
    
    graph = build_graph()
    
    initial_state = {
        "messages": [("user", user_input)],
        "plan_iterations": 0,
        "observations": [],
        "resources": [],
        "verbosity": 3,
    }
    
    config = {
        "configurable": {
            "max_plan_iterations": 2, 
            "max_search_results": 2,
            "snaptrade_settings": {
                "MOCK_BROKER": "true"
            }
        },
        "recursion_limit": 50,
    }
    
    final_state = None
    async for event in graph.astream(initial_state, config=config, stream_mode="values"):
        final_state = event
        
    print("\n" + "="*50)
    print("FINAL TREND CONSISTENCY REPORT:")
    if final_state and "final_report" in final_state:
        print(final_state["final_report"][:4000])
    else:
        print("No final report generated.")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
