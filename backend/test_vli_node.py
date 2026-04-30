import asyncio
from src.graph.nodes.vli import vli_node
from langchain_core.runnables import RunnableConfig

async def test():
    state = {'messages': [], 'current_plan': '', 'raw_data_mode': False}
    config = RunnableConfig()
    try:
        res = await vli_node(state, config)
        print("RETURNED SUCCESSFULLY:")
        print(type(res))
        print("Update Keys:", res.update.keys())
        print("Goto:", res.goto)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
