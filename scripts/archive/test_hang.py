import asyncio
import os
import json
from src.graph.builder import build_graph_with_memory
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)

load_dotenv()

async def main():
    graph = build_graph_with_memory()
    config = {"configurable": {"thread_id": "test_thread_1"}}
    
    print("Graph built. Starting execution...")
    
    state_input = {
        "messages": [HumanMessage(content="what is AAPL stock price?")]
    }
    
    try:
        async for chunk in graph.astream(state_input, config=config):
            print("====================================")
            for key, value in chunk.items():
                print(f"Node execution returned from: {key}")
                if value is None:
                    continue
                if "messages" in value:
                    print(f"Message from {key}: {value['messages'][-1].content[:200]}")
                if "current_plan" in value:
                    print(f"Plan updated. Steps fully executed? {all(s.execution_res for s in value['current_plan'].steps) if hasattr(value['current_plan'], 'steps') else 'N/A'}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
