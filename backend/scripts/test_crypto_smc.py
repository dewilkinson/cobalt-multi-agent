import asyncio
import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.tools.finance import run_smc_analysis

async def main():
    print("Testing XRPUSDT...")
    try:
        r_func = getattr(run_smc_analysis, "coroutine", getattr(run_smc_analysis, "func", None))
        res = await r_func(ticker="XRPUSDT", interval="auto")
        print(res)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
