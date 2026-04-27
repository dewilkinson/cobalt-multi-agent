import asyncio
import sys
import os
import logging
sys.path.append(os.path.dirname(__file__))
from src.tools.news import get_ticker_news

async def main():
    res = await get_ticker_news.ainvoke({'subject': 'AMZN', 'refresh': True})
    print('News Res:', res[:1500])

if __name__ == '__main__':
    asyncio.run(main())
