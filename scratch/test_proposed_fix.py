import asyncio
import os
import sys
import pandas as pd
from zoneinfo import ZoneInfo

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

# Force yfinance provider to simulate the user environment
os.environ["DATA_PROVIDER"] = "yfinance"

from src.tools.finance import _fetch_batch_history, _extract_ticker_data
from src.tools.macros import macro_registry, NY_TZ, MACRO_NAMES

async def main():
    tickers = list(macro_registry.get_macros().values())
    print("Tickers:", tickers)
    
    # Proposed configuration
    _INTERVAL = "1d"
    _LOOKBACK = 10
    
    # Use 15d period to ensure we get at least 10 trading days (excluding weekends)
    sparkline_data = await asyncio.to_thread(_fetch_batch_history, tickers, "15d", _INTERVAL)
    
    yahoo_ticker = "QQQ"
    ticker_spark_df = _extract_ticker_data(sparkline_data, yahoo_ticker)
    
    # Sort index chronologically
    ticker_spark_df = ticker_spark_df.sort_index()
    
    change_pct = 0.0
    sparkline = []
    
    if not ticker_spark_df.empty:
        # Calculate daily change percent from last two daily closes
        if len(ticker_spark_df) > 1:
            prev_close = float(ticker_spark_df.iloc[-2]["Close"])
            curr_close = float(ticker_spark_df.iloc[-1]["Close"])
            if prev_close > 0:
                change_pct = ((curr_close - prev_close) / prev_close) * 100
                
        # Take last _LOOKBACK values
        last_n = ticker_spark_df.tail(_LOOKBACK)
        for _, row in last_n.iterrows():
            ts = row.name
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=ZoneInfo("UTC"))
            
            # Format as just Date if daily, otherwise Date + Time
            if _INTERVAL == "1d":
                date_str = ts.astimezone(NY_TZ).strftime(" %m/%d").lower()
            else:
                date_str = ts.astimezone(NY_TZ).strftime(" %m/%d  %I:%M %p").lower()
                
            sparkline.append({"v": float(row["Close"]), "t": date_str})
            
    print("\nCalculated Daily Change % for QQQ:", change_pct)
    print("Sparkline points:")
    for pt in sparkline:
        print(pt)

if __name__ == "__main__":
    asyncio.run(main())
