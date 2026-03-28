import asyncio
from backend.src.tools.finance import get_stock_quote
from backend.src.tools.smc import get_smc_analysis

async def test():
    res = await get_stock_quote.ainvoke({"ticker": "SPY", "period": "1d", "interval": "1m"})
    print("--- QUOTE ---")
    print(res)
    print("--- END QUOTE ---")

if __name__ == "__main__":
    asyncio.run(test())
