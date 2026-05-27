import asyncio
import os
import sys

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from src.tools.news import get_ticker_news

async def main():
    res = await get_ticker_news.ainvoke({"ticker": "VSH", "refresh": True})
    with open("news_out.txt", "w", encoding="utf-8") as f:
        f.write(res)

if __name__ == "__main__":
    asyncio.run(main())
