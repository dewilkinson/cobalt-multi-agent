import asyncio
import sys
import os
import logging
sys.path.append(os.path.dirname(__file__))
from src.tools.news import get_ticker_news
from src.tools.finance import get_stock_quote

async def run_gather():
    print("Gathering NVDA data...")
    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                get_ticker_news.ainvoke({"subject": "NVDA", "refresh": True}),
                get_stock_quote.ainvoke({"ticker": "NVDA", "force_refresh": True}),
                return_exceptions=True
            ),
            timeout=30.0
        )
        print("Gather completed:", type(results), len(results))
        for r in results:
            print(" -> Result type:", type(r))
            if isinstance(r, Exception):
                print(" -> Exception:", r)
    except Exception as e:
        print("Gather exception:", type(e), e)

if __name__ == "__main__":
    asyncio.run(run_gather())
