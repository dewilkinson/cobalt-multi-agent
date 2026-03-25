import asyncio
import yfinance as yf
import pandas as pd
import numpy as np
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.tools.smc import get_smc_analysis

async def verify_smc():
    symbol = "GLDM"
    print(f"=== Testing SMC Logic for {symbol} ===")
    res = await get_smc_analysis.ainvoke({"ticker": symbol})
    print(res)

if __name__ == "__main__":
    asyncio.run(verify_smc())
