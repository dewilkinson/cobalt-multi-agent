import asyncio
import sys
import os

sys.path.append(os.path.dirname(__file__))

from src.tools import get_sortino_ratio

async def main():
    print('LLM Sortino STM:')
    print(await get_sortino_ratio.ainvoke({"ticker": "STM"}))

if __name__ == '__main__':
    asyncio.run(main())
