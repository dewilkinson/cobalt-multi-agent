import asyncio
import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from src.utils.temporal import set_reference_time, get_effective_now
from src.tools.news import get_ticker_news

async def main():
    ref_time = datetime(2026, 6, 12, 11, 42, 19)
    set_reference_time(ref_time)
    print("Effective now is:", get_effective_now())
    
    print("\n================ FETCHING NEWS FOR CRWV ================")
    try:
        res = await get_ticker_news.ainvoke({"ticker": "CRWV", "refresh": True})
        print(res)
    except Exception as e:
        print(f"Error fetching news for CRWV: {e}")

if __name__ == "__main__":
    asyncio.run(main())
