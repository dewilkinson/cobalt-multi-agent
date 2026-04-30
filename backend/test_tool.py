import asyncio
import sys
import os
import logging
sys.path.append(os.path.dirname(__file__))
from src.tools.news import get_ticker_news
from src.tools.finance import get_stock_quote

async def main():
    print('Calling get_ticker_news')
    try:
        res = get_ticker_news('ARM', refresh=True)
        print('News Res:', type(res))
    except Exception as e:
        print('News Error:', type(e), e)
        
    print('Calling get_stock_quote')
    try:
        res = get_stock_quote('ARM', force_refresh=True)
        print('Quote Res:', type(res))
    except Exception as e:
        print('Quote Error:', type(e), e)

if __name__ == '__main__':
    asyncio.run(main())
