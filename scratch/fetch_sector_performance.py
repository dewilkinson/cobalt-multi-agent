import os
import sys
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from src.tools.finance import _fetch_replay_history

def main():
    end_date = datetime(2026, 6, 12, 12, 5, 0)
    
    # Major Sector ETFs
    sectors = {
        "XLK": "Technology",
        "XLC": "Communication Services",
        "XLY": "Consumer Discretionary",
        "XLF": "Financials",
        "XLV": "Healthcare",
        "XLI": "Industrials",
        "XLE": "Energy",
        "XLB": "Materials",
        "XLU": "Utilities",
        "XLRE": "Real Estate",
        "XLP": "Consumer Staples",
        "SOXX": "Semiconductors"
    }
    
    tickers = list(sectors.keys())
    
    print(f"Fetching intraday data for sectors up to {end_date}...")
    try:
        # Fetch today's data (using 5m bars for accuracy of today's open to current)
        df = _fetch_replay_history(tickers, period="1d", interval="5m", end_date=end_date)
        if df.empty:
            print("No data returned!")
            return
            
        df.index = pd.to_datetime(df.index)
        
        results = []
        for ticker in tickers:
            ticker_df = df[ticker].copy()
            today_bars = ticker_df[ticker_df.index.date == datetime(2026, 6, 12).date()]
            if today_bars.empty:
                continue
                
            open_val = today_bars.iloc[0]["Open"]
            close_val = today_bars.iloc[-1]["Close"]
            high_val = today_bars["High"].max()
            low_val = today_bars["Low"].min()
            
            net_change = ((close_val - open_val) / open_val) * 100
            daily_range = ((high_val - low_val) / open_val) * 100
            
            results.append({
                "Ticker": ticker,
                "Sector": sectors[ticker],
                "Open": open_val,
                "Current": close_val,
                "Change %": net_change,
                "Range %": daily_range
            })
            
        # Convert to DataFrame and sort by performance
        res_df = pd.DataFrame(results).sort_values(by="Change %", ascending=False)
        print("\n================ SECTOR PERFORMANCE SUMMARY (JUNE 12, 2026) ================")
        print(res_df.to_string(index=False, formatters={
            "Open": "{:.2f}".format,
            "Current": "{:.2f}".format,
            "Change %": "{:+.2f}%".format,
            "Range %": "{:.2f}%".format
        }))
        
    except Exception as e:
        print(f"Error fetching sector data: {e}")

if __name__ == "__main__":
    main()
