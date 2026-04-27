import asyncio
import sys
import os

sys.path.append(os.path.dirname(__file__))

from src.tools.scanner import batch_fetch_sortino
from src.tools.finance import get_sortino_ratio

async def main():
    print('Scanner Sortino:')
    print(await batch_fetch_sortino(['STM', 'GFS'], period="20d"))
    
    print('LLM Sortino STM:')
    print(await get_sortino_ratio.ainvoke({"ticker": "STM"}))
    
    print('LLM Sortino GFS:')
    print(await get_sortino_ratio.ainvoke({"ticker": "GFS"}))

if __name__ == '__main__':
    asyncio.run(main())
