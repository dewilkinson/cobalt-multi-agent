import asyncio
import os
import sys
import pandas as pd
from zoneinfo import ZoneInfo

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

# Force yfinance provider
os.environ["DATA_PROVIDER"] = "yfinance"

from src.tools.finance import _fetch_batch_history, _extract_ticker_data
from src.tools.macros import macro_registry, NY_TZ

async def main():
    tickers = list(macro_registry.get_macros().values())
    print("Tickers in registry:", tickers)
    
    sparkline_data = await asyncio.to_thread(_fetch_batch_history, tickers, "5d", "1h")
    
    yahoo_ticker = "QQQ"
    ticker_spark_df = _extract_ticker_data(sparkline_data, yahoo_ticker)
    
    print("\n--- Raw extracted QQQ df (tail 15) ---")
    print(ticker_spark_df.tail(15))
    
    print("\n--- Iterating over tail(10) ---")
    last_n = ticker_spark_df.tail(10)
    for idx, row in last_n.iterrows():
        ts = idx
        ts_utc = ts
        if ts.tzinfo is None:
            ts_utc = ts.replace(tzinfo=ZoneInfo("UTC"))
        
        formatted = ts_utc.astimezone(NY_TZ).strftime(" %m/%d  %I:%M %p").lower()
        print(f"Index: {idx} | Close: {row['Close']} | Formatted: {formatted}")

if __name__ == "__main__":
    asyncio.run(main())
