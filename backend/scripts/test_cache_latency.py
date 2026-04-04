import asyncio
import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.tools.finance import get_sharpe_ratio, get_sortino_ratio, run_smc_analysis

async def main():
    print("Executing first batch of tools (Uncached)")
    t1 = time.time()
    await get_sharpe_ratio.coroutine("XRPUSDT")
    await get_sortino_ratio.coroutine("XRPUSDT")
    res1 = await getattr(run_smc_analysis, "coroutine", getattr(run_smc_analysis, "func", None))(ticker="XRPUSDT", interval="auto")
    t2 = time.time()
    print(f"First run duration (Network + 3s sleep logic): {t2 - t1:.2f}s")
    
    print("\nExecuting second batch of tools (Cached)")
    t3 = time.time()
    await get_sharpe_ratio.coroutine("XRPUSDT")
    await get_sortino_ratio.coroutine("XRPUSDT")
    res2 = await getattr(run_smc_analysis, "coroutine", getattr(run_smc_analysis, "func", None))(ticker="XRPUSDT", interval="auto")
    t4 = time.time()
    print(f"Second run duration (Should be near 0s): {t4 - t3:.2f}s")
    print("\nVerification successful if second run is practically instant!")

if __name__ == "__main__":
    asyncio.run(main())
