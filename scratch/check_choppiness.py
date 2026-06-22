import os
import sys
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from src.tools.finance import _fetch_replay_history

def main():
    end_date = datetime(2026, 6, 12, 11, 55, 0)
    # We download 1-minute data for the day
    tickers = ["SPY", "QQQ"]
    
    print(f"Fetching intraday data for SPY and QQQ up to {end_date}...")
    try:
        df = _fetch_replay_history(tickers, period="1d", interval="5m", end_date=end_date)
        if df.empty:
            print("No data returned!")
            return
            
        df.index = pd.to_datetime(df.index)
        
        for t in tickers:
            print(f"\n================ INTRADAY SUMMARY FOR {t} ================")
            ticker_df = df[t].copy()
            
            # Intraday bars for June 12 (today)
            today_bars = ticker_df[ticker_df.index.date == datetime(2026, 6, 12).date()]
            if today_bars.empty:
                print("No intraday bars found for today.")
                continue
                
            open_val = today_bars.iloc[0]["Open"]
            high_val = today_bars["High"].max()
            low_val = today_bars["Low"].min()
            close_val = today_bars.iloc[-1]["Close"]
            
            total_range = high_val - low_val
            pct_range = (total_range / open_val) * 100
            net_change = ((close_val - open_val) / open_val) * 100
            
            print(f"Market Open: {open_val:.2f}")
            print(f"Daily High:  {high_val:.2f}")
            print(f"Daily Low:   {low_val:.2f}")
            print(f"Current (11:50 AM): {close_val:.2f}")
            print(f"Daily Range: {total_range:.2f} ({pct_range:.2f}%)")
            print(f"Net Change:  {net_change:+.2f}%")
            
            # Let's count direction switches in 5m bars to assess choppiness
            changes = today_bars["Close"].diff().dropna()
            signs = [1 if x > 0 else -1 for x in changes if x != 0]
            reversals = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i-1])
            print(f"Reversals (Direction Switches): {reversals} (out of {len(changes)} periods)")
            
            # Print recent 5-minute bars to see the trajectory
            print("\nRecent 5m Candles:")
            for idx, row in today_bars.tail(8).iterrows():
                print(f"Time: {idx.time()} | O: {row['Open']:.2f} | H: {row['High']:.2f} | L: {row['Low']:.2f} | C: {row['Close']:.2f}")
                
    except Exception as e:
        print(f"Failed to fetch data: {e}")

if __name__ == "__main__":
    main()
