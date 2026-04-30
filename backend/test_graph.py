import asyncio
from src.graph.builder import build_graph
from langchain_core.messages import HumanMessage

async def test():
    g = build_graph()
    try:
        res = await g.ainvoke({'messages': [HumanMessage(content="Fast Price for MSFT")], 'current_plan': '', 'raw_data_mode': False})
        print(res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
