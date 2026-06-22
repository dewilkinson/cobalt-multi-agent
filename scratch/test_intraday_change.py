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
    tickers = ["SPY", "QQQ", "IWM", "BTC-USD"]
    
    _INTERVAL = "15m"
    _LOOKBACK = 10
    
    print(f"Fetching {_INTERVAL} data for {tickers}...")
    sparkline_data = await asyncio.to_thread(_fetch_batch_history, tickers, "5d", _INTERVAL)
    
    for yahoo_ticker in tickers:
        print(f"\n================ {yahoo_ticker} ================")
        ticker_spark_df = _extract_ticker_data(sparkline_data, yahoo_ticker)
        if ticker_spark_df.empty:
            print("No data extracted!")
            continue
            
        ticker_spark_df = ticker_spark_df.sort_index()
        
        # Convert index to NY Time
        try:
            ticker_spark_df.index = pd.to_datetime(ticker_spark_df.index, utc=True).tz_convert(NY_TZ).tz_localize(None)
        except Exception:
            ticker_spark_df.index = pd.to_datetime(ticker_spark_df.index).tz_localize(None)
            
        latest_date = ticker_spark_df.index[-1].date()
        print(f"Latest Date: {latest_date}")
        
        # Filter for today's session (including pre/post market)
        day_df = ticker_spark_df[ticker_spark_df.index.date == latest_date]
            
        # Get current price
        col = "Close" if "Close" in ticker_spark_df.columns else "close"
        current_price = float(ticker_spark_df[col].dropna().iloc[-1])
        
        # Calculate daily change percent (relative to yesterday's close)
        change_pct = 0.0
        unique_dates = sorted(list(set(ticker_spark_df.index.date)))
        print(f"Unique Dates in data: {unique_dates}")
        if len(unique_dates) > 1:
            prev_date = unique_dates[-2]
            prev_day_df = ticker_spark_df[ticker_spark_df.index.date == prev_date]
            prev_day_close = prev_day_df[col].dropna()
            if not prev_day_close.empty:
                yesterday_close = float(prev_day_close.iloc[-1])
                change_pct = ((current_price - yesterday_close) / yesterday_close) * 100
                print(f"Yesterday's Date: {prev_date} | Yesterday's Close: {yesterday_close:.2f} | Current Price: {current_price:.2f}")
        else:
            first_close = float(day_df[col].dropna().iloc[0]) if not day_df.empty else current_price
            change_pct = ((current_price - first_close) / first_close) * 100
            print(f"No yesterday data. First bar of today: {first_close:.2f} | Current Price: {current_price:.2f}")
            
        # Sparkline points
        sparkline = []
        target_data = day_df[col].dropna()
        if isinstance(target_data, pd.DataFrame):
            target_data = target_data.iloc[:, 0]
            
        if not target_data.empty:
            indices = np.linspace(0, len(target_data) - 1, _LOOKBACK, dtype=int)
            for idx in indices:
                row_time = target_data.index[idx]
                val = float(target_data.iloc[idx])
                t_str = row_time.strftime(" %I:%M %p").lower()
                sparkline.append({"v": val, "t": t_str})
            sparkline[-1]["v"] = current_price
            
        print(f"Daily Change %: {change_pct:+.4f}%")
        print(f"Sparkline points ({len(sparkline)}):")
        for pt in sparkline:
            print(f"  Value: {pt['v']:.2f} | Time: {pt['t']}")

if __name__ == "__main__":
    asyncio.run(test())
