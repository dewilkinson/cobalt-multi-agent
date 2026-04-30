import asyncio
from src.graph.builder import build_graph
from langchain_core.messages import HumanMessage
import time

async def main():
    app = build_graph()
    
    print("--- RUN 1 (COLD) ---")
    state = {"messages": [HumanMessage(content="Analyze RIVN")], "locale": "en-US", "research_topic": "RIVN", "final_report": "", "raw_data_mode": False}
    try:
        async for _ in app.astream(state, {"recursion_limit": 50}):
            pass
    except Exception as e:
        print("Run 1 ERR:", e)
        
    print("--- RUN 2 (WARM) ---")
    state = {"messages": [HumanMessage(content="Analyze RIVN")], "locale": "en-US", "research_topic": "RIVN", "final_report": "", "raw_data_mode": False}
    try:
        async for _ in app.astream(state, {"recursion_limit": 50}):
            pass
    except Exception as e:
        print("Run 2 ERR:", e)
        
if __name__ == "__main__":
    asyncio.run(main())
