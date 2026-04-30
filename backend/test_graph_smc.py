import asyncio
import sys
import logging

sys.path.insert(0, './')

from langchain_core.messages import HumanMessage
from src.graph.builder import graph

logging.basicConfig(level=logging.INFO)

async def main():
    config = {"configurable": {"thread_id": "test_deep_smc_issue"}}
    
    workflow_input = {
        "messages": [HumanMessage(content="Analyze deep organizational SMC structures for MSFT")],
        "direct_mode": False
    }
    
    print("Invoking graph...")
    final_state = await graph.ainvoke(workflow_input, config)
    print("="*50)
    print("FINAL REPORT:")
    if "final_report" in final_state:
        print(final_state["final_report"])
    else:
        print("NO FINAL REPORT GENERATED!")
        for m in final_state.get("messages", []):
            print(f"MSG [{m.name if hasattr(m, 'name') else 'user'}]: {m.content}")

if __name__ == "__main__":
    asyncio.run(main())
