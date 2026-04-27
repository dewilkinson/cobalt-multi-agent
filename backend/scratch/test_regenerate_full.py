import asyncio
import logging
from src.server.app import _background_regenerate_data
from src.tools.finance import get_stock_quote
from src.tools.news import get_ticker_news

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_regenerate(sym="ARM"):
    print(f"=== Testing _background_regenerate_data({sym}) ===")
    
    # 1. Directly invoke the tools to see if they fail or succeed
    print("\n--- Testing get_stock_quote ---")
    try:
        quote_res = await get_stock_quote.ainvoke({"ticker": sym, "force_refresh": True})
        print(f"Quote Success! Length of output: {len(str(quote_res))}")
        print("Preview:", str(quote_res)[:150])
    except Exception as e:
        print(f"Quote Failed! Error: {e}")

    print("\n--- Testing get_ticker_news ---")
    try:
        news_res = await get_ticker_news.ainvoke({"subject": sym})
        print(f"News Success! Length of output: {len(str(news_res))}")
        print("Preview:", str(news_res)[:150])
    except Exception as e:
        print(f"News Failed! Error: {e}")
        
    print("\n--- Testing _background_regenerate_data Wrapper ---")
    try:
        await _background_regenerate_data(sym)
        print("Wrapper launched successfully.")
    except Exception as e:
        print("Wrapper Failed!", e)

if __name__ == "__main__":
    asyncio.run(test_regenerate())
