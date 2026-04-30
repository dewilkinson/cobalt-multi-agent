import asyncio
import sys
import logging

sys.path.insert(0, './')

from langchain_core.messages import HumanMessage
from src.graph.nodes.smc_analyst import smc_analyst_node

logging.basicConfig(level=logging.INFO)

async def main():
    config = {"configurable": {"thread_id": "test_deep_smc_node"}}
    state = {
        "messages": [HumanMessage(content="Perform the full get smc analysis for MSFT")],
        "current_plan": None
    }
    
    print("Directly invoking SMC Analyst node...")
    res = await smc_analyst_node(state, config)
    print("="*50)
    print("SMC ANALYST NODE RETURNED:")
    for m in res.get("messages", []):
        name = getattr(m, 'name', 'user')
        content = getattr(m, 'content', '')
        print(f"MSG [{name}]: {content}")

if __name__ == "__main__":
    asyncio.run(main())
