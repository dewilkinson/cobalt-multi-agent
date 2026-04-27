import asyncio
import sys
import os
import logging
sys.path.append(os.path.dirname(__file__))
from src.tools.news import get_ticker_news
from src.tools.finance import get_stock_quote

async def main():
    print('Calling get_ticker_news NVDA')
    try:
        res = await asyncio.wait_for(get_ticker_news.ainvoke({'subject': 'NVDA', 'refresh': True}), timeout=10)
        print('News Res Length:', len(str(res)))
    except Exception as e:
        print('News Error:', type(e), e)
        
    print('Calling get_stock_quote NVDA')
    try:
        res2 = await asyncio.wait_for(get_stock_quote.ainvoke({'ticker': 'NVDA', 'force_refresh': True}), timeout=10)
        print('Quote Res Length:', len(str(res2)))
    except Exception as e:
        print('Quote Error:', type(e), e)

if __name__ == '__main__':
    asyncio.run(main())
