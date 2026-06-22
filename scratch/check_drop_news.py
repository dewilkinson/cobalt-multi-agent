import asyncio
import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from src.utils.temporal import set_reference_time, get_effective_now
from src.tools.news import get_ticker_news
from src.tools.search import get_web_search_tool

async def main():
    # Set the simulated current time to June 12, 2026 at 11:42:19 AM
    # This aligns the environment time for get_effective_now()
    ref_time = datetime(2026, 6, 12, 11, 42, 19)
    set_reference_time(ref_time)
    print("Effective now is:", get_effective_now())
    
    tickers = ["INTC", "AMAT", "ARM", "CRWD"]
    for t in tickers:
        print(f"\n================ FETCHING NEWS FOR {t} ================")
        try:
            res = await get_ticker_news.ainvoke({"ticker": t, "refresh": True})
            print(res[:1500])  # Print first 1500 chars
        except Exception as e:
            print(f"Error fetching news for {t}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
