import asyncio
import sys

sys.path.insert(0, './')
from src.tools.finance import run_smc_analysis

async def main():
    print(await run_smc_analysis.coroutine('MSFT', interval='auto'))

if __name__ == "__main__":
    asyncio.run(main())
