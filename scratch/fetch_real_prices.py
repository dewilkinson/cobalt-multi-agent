import os
import sys
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from src.tools.finance import _fetch_replay_history

def main():
    # Target date is Friday, June 12, 2026
    # Let's fetch 1-minute data for the day up to 11:45 AM
    end_date = datetime(2026, 6, 12, 11, 46, 0)
    tickers = ["SPY", "QQQ", "INTC", "AMAT", "ARM", "CRWV"]
    
    print(f"Fetching 1m bars ending at {end_date}...")
    try:
        # Download 1-minute data for 1 day
        df = _fetch_replay_history(tickers, period="1d", interval="1m", end_date=end_date)
        if df.empty:
            print("No data returned!")
            return
            
        print("\nColumns in DataFrame:", df.columns)
        
        # Let's inspect the data for each ticker between 11:30 and 11:45
        for t in tickers:
            print(f"\n================ 1-MINUTE CHART FOR {t} ================")
            try:
                # yfinance return multi-index if multiple tickers
                if len(tickers) > 1:
                    ticker_df = df[t]
                else:
                    ticker_df = df
                
                # Filter for times between 11:30 and 11:45
                ticker_df = ticker_df.copy()
                # Ensure index is datetime
                ticker_df.index = pd.to_datetime(ticker_df.index)
                
                # Filter rows
                window = ticker_df[(ticker_df.index.time >= datetime(2026,6,12,11,30).time()) & 
                                   (ticker_df.index.time <= datetime(2026,6,12,11,46).time())]
                
                if window.empty:
                    print("No data in the 11:30 - 11:46 window. Printing last 10 rows of available data:")
                    print(ticker_df.tail(10))
                else:
                    for idx, row in window.iterrows():
                        print(f"Time: {idx.time()} | Open: {row['Open']:.2f} | High: {row['High']:.2f} | Low: {row['Low']:.2f} | Close: {row['Close']:.2f} | Volume: {row['Volume']}")
            except Exception as e:
                print(f"Error printing data for {t}: {e}")
                
    except Exception as e:
        print(f"Failed to fetch: {e}")

if __name__ == "__main__":
    main()
