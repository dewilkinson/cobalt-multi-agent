import asyncio
import sys
import os
import logging
sys.path.append(os.path.dirname(__file__))
from src.tools.news import get_ticker_news
from src.tools.finance import get_stock_quote

async def main():
    res = await get_stock_quote.ainvoke({'ticker': 'NVDA', 'force_refresh': True})
    print('Quote Res:', res)

if __name__ == '__main__':
    asyncio.run(main())
