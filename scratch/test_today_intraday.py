import asyncio
import os
import sys
import pandas as pd
import numpy as np
import datetime as dt
from zoneinfo import ZoneInfo

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

# Force yfinance provider
os.environ["DATA_PROVIDER"] = "yfinance"

from src.tools.finance import _fetch_batch_history, _extract_ticker_data
from src.tools.macros import macro_registry, NY_TZ

async def test():
    tickers = ["SPY", "QQQ", "IWM"]
    
    # Fetch intraday data: 2d period, 5m or 1m interval
    # 5m interval is faster and covers today's session sufficiently
    print("Fetching 5m data for SPY, QQQ, IWM...")
    sparkline_data = await asyncio.to_thread(_fetch_batch_history, tickers, "2d", "5m")
    
    for ticker in tickers:
        print(f"\n=== Ticker: {ticker} ===")
        sparkline_df = _extract_ticker_data(sparkline_data, ticker)
        if sparkline_df.empty:
            print("No data extracted!")
            continue
            
        sparkline_df = sparkline_df.sort_index()
        
        # Convert index to NY Time
        try:
            ny_index = pd.to_datetime(sparkline_df.index, utc=True).tz_convert('America/New_York').tz_localize(None)
        except Exception:
            ny_index = pd.to_datetime(sparkline_df.index).tz_localize(None)
        sparkline_df.index = ny_index
        
        latest_date = sparkline_df.index[-1].date()
        print(f"Latest Date in Data: {latest_date}")
        
        # Filter for only this day
        day_df = sparkline_df[sparkline_df.index.date == latest_date]
        
        # Filter for after 9:30 AM NY time
        day_df = day_df[day_df.index.time >= dt.time(9, 30)]
        print(f"Number of bars today after 9:30 AM: {len(day_df)}")
        
        col = "Close" if "Close" in day_df.columns else "close"
        target_data = day_df[col].dropna()
        if isinstance(target_data, pd.DataFrame):
            target_data = target_data.iloc[:, 0]
            
        if not target_data.empty:
            num_points = 10
            indices = np.linspace(0, len(target_data) - 1, num_points, dtype=int)
            values = target_data.iloc[indices].tolist()
            output_values = [round(float(v), 2) for v in values]
            
            print("Sparkline values (10 points):", output_values)
            print("First bar time:", day_df.index[indices[0]])
            print("Last bar time:", day_df.index[indices[-1]])

if __name__ == "__main__":
    asyncio.run(test())
