import asyncio
import os
import json
from src.tools.finance import get_stock_quote

async def verify_fallback():
    # Triggering a failure by passing a symbol that is partially valid but broken for yf downloads
    # Or just mocking a failure in the tool call if I could, but let's try a real "failed" ticker.
    ticker = "INVALID_TICKER_99"
    print(f"DEBUG: Testing fallback for {ticker}...")
    
    try:
        # Note: calling the .func attribute because it's a @tool
        result = await get_stock_quote.func(ticker)
        
        # We expect it to reach the fallback after failing yf
        if isinstance(result, dict) and result.get("source") == "Visual TradingView Snapshot (Fallback)":
            print("DEBUG: SUCCESS - Fallback deployed correctly.")
            print(f"DEBUG: Symbol: {result['symbol']}")
            print(f"DEBUG: Images Captured: {len(result.get('images', []))}")
        else:
            print(f"DEBUG: Result did not use fallback: {result}")
    except Exception as e:
        print(f"DEBUG: EXCEPTION - {str(e)}")

if __name__ == "__main__":
    asyncio.run(verify_fallback())
