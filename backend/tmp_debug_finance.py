import yfinance as yf
import asyncio
import pandas as pd

async def debug_vix():
    symbol = "^VIX"
    print(f"DEBUG: Attempting to download {symbol} via yfinance...")
    try:
        # Test download with 1d period
        df = yf.download(symbol, period="1d", interval="1m", progress=False)
        if df.empty:
            print(f"DEBUG: FAILURE - DataFrame for {symbol} is empty.")
        else:
            print(f"DEBUG: SUCCESS - Fetched data for {symbol}:")
            print(df.tail())
            
        ticker = yf.Ticker(symbol)
        info = ticker.info
        print(f"DEBUG: Ticker Info Keys: {list(info.keys())[:10]}...")
        print(f"DEBUG: Current Price (info): {info.get('regularMarketPrice')}")
        
    except Exception as e:
        print(f"DEBUG: EXCEPTION - {str(e)}")

if __name__ == "__main__":
    asyncio.run(debug_vix())
