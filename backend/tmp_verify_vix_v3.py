import asyncio
import pandas as pd
from src.tools.finance import _normalize_ticker, _fetch_batch_history, _extract_ticker_data

async def verify_vix_raw():
    ticker = "VIX"
    norm = _normalize_ticker(ticker)
    print(f"DEBUG: Normalized {ticker} -> {norm}")
    
    try:
        print(f"DEBUG: Fetching {norm}...")
        # Use sync call for _fetch_batch_history as it's a sync function wrapper
        df = _fetch_batch_history([norm], period="1d", interval="1m")
        
        print("DEBUG: Extracting data...")
        ticker_df = _extract_ticker_data(df, norm)
        
        if ticker_df.empty:
            print("DEBUG: FAILURE - Dataframe is empty.")
        else:
            last_row = ticker_df.iloc[-1]
            print(f"DEBUG: SUCCESS - Price for {norm}: {last_row['Close']:.2f}")
    except Exception as e:
        print(f"DEBUG: EXCEPTION - {str(e)}")

if __name__ == "__main__":
    asyncio.run(verify_vix_raw())
