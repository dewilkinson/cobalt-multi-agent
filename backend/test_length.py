import asyncio, sys, json
sys.path.insert(0, './')
from src.tools.smc import get_smc_analysis
async def main():
    res=await get_smc_analysis.coroutine('MSFT', period='1y', interval='1d')
    print('RAW LENGTH:', len(res))
    print('LIST SIZE:', len(json.loads(res)))
asyncio.run(main())
