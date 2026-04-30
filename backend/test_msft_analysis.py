import asyncio
import traceback
from src.graph.builder import build_graph
from langchain_core.messages import HumanMessage

async def test():
    g = build_graph()
    try:
        # We want to test 'analyze MSFT' instead of 'Fast Price for MSFT' to trigger full synthesis
        res = await g.ainvoke({'messages': [HumanMessage(content="analyze MSFT")], 'current_plan': '', 'raw_data_mode': False})
        print("====== RESULT ======")
        print(res)
    except Exception as e:
        print("====== EXCEPTION CAUGHT ======")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
