import asyncio
from src.tools.finance import run_smc_analysis

async def test():
    f = getattr(run_smc_analysis, 'coroutine', None)
    print(await f("GLDM", "1h"))

if __name__ == "__main__":
    asyncio.run(test())
