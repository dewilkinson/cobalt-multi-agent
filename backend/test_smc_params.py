import asyncio
import sys

sys.path.insert(0, './')
from src.tools.smc import get_smc_analysis

async def main():
    print("Testing 1y 1d...")
    res = await get_smc_analysis.coroutine(ticker="MSFT", period="1y", interval="1d")
    print(f"Len: {len(res)}, snippet: {res[:20]}")
    
    print("Testing 5d 5m...")
    res = await get_smc_analysis.coroutine(ticker="MSFT", period="5d", interval="5m")
    print(f"Len: {len(res)}, snippet: {res[:20]}")

    print("Testing 1mo 1h...")
    res = await get_smc_analysis.coroutine(ticker="MSFT", period="1mo", interval="1h")
    print(f"Len: {len(res)}, snippet: {res[:20]}")

if __name__ == "__main__":
    asyncio.run(main())
