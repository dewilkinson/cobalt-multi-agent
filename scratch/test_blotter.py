import sys
import os
import asyncio

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from src.tools.broker import get_daily_blotter
from langchain_core.runnables import RunnableConfig

async def main():
    config = RunnableConfig(configurable={})
    res = await get_daily_blotter.ainvoke({}, config=config)
    print(res)

if __name__ == "__main__":
    asyncio.run(main())
