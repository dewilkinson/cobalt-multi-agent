import asyncio
import sys
import os

sys.path.append(os.path.dirname(__file__))

from src.tools.smc import get_smc_analysis

async def main():
    print('LLM SMC STM:')
    print(await get_smc_analysis.ainvoke({"ticker": "STM"}))

if __name__ == '__main__':
    asyncio.run(main())
