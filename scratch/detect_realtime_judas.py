import yfinance as yf
import pandas as pd
import numpy as np
import pytz
from datetime import datetime

def scan_realtime_day(ticker, day_str, df):
    # Filter for the specific day
    day_df = df[df.index.strftime('%Y-%m-%d') == day_str]
    if day_df.empty:
        return None
        
    # Localize to US/Eastern
    est = pytz.timezone('America/New_York')
    day_df = day_df.tz_convert(est)
    
    # Regular trading hours (09:30 to 16:00 EST)
    rth_df = day_df.between_time('09:30', '16:00')
    if rth_df.empty:
        return None
        
    # We will iterate through the 5m bars sequentially
    open_price = float(rth_df['Open'].iloc[0])
    
    state = "LOOKING_FOR_DIP"
    stop_hunt_low = None
    stop_hunt_time = None
    trigger_time = None
    confirm_count = 0
    
    cutoff_first_hour = datetime.strptime("10:30", "%H:%M").time()
    
    for idx in range(len(rth_df)):
        row = rth_df.iloc[idx]
        t = rth_df.index[idx]
        t_time = t.time()
        
        low_val = float(row['Low'])
        close_val = float(row['Close'])
        
        # 1. Look for a stop hunt low in the first hour
        if t_time <= cutoff_first_hour:
            if low_val < open_price:
                if stop_hunt_low is None or low_val < stop_hunt_low:
                    stop_hunt_low = low_val
                    stop_hunt_time = t
                    state = "LOOKING_FOR_REVERSAL"
                    confirm_count = 0
                    
        # 2. Look for reversal back above the open price
        if state == "LOOKING_FOR_REVERSAL":
            if t > stop_hunt_time:
                # If we break the low, update it if still within first hour
                if low_val < stop_hunt_low:
                    if t_time <= cutoff_first_hour:
                        stop_hunt_low = low_val
                        stop_hunt_time = t
                    else:
                        # Broke low after first hour, invalidates the pattern
                        state = "LOOKING_FOR_DIP"
                        stop_hunt_low = None
                        stop_hunt_time = None
                        continue
                
                # Check if close is above open to trigger
                if close_val > open_price:
                    trigger_time = t
                    state = "CONFIRMING"
                    confirm_count = 0
                    
        # 3. Confirm for 2 subsequent candles
        elif state == "CONFIRMING":
            # If we break the stop hunt low, it's invalidated
            if low_val <= stop_hunt_low:
                state = "LOOKING_FOR_DIP"
                stop_hunt_low = None
                stop_hunt_time = None
                trigger_time = None
                continue
                
            if close_val > open_price:
                confirm_count += 1
                if confirm_count == 2:
                    # Confirmed! Return the event details
                    pct_drop = ((open_price - stop_hunt_low) / open_price) * 100
                    return {
                        'date': day_str,
                        'open': open_price,
                        'stop_hunt_low': stop_hunt_low,
                        'stop_hunt_time': stop_hunt_time.strftime('%H:%M'),
                        'trigger_time': trigger_time.strftime('%H:%M'),
                        'confirm_time': t.strftime('%H:%M'),
                        'confirm_price': close_val,
                        'pct_drop': pct_drop
                    }
            else:
                # If it closes below open during confirmation, reset confirmation count
                # but keep looking for reversal unless it breaks the low
                confirm_count = 0
                state = "LOOKING_FOR_REVERSAL"
                
    return None

def to_md_table(df):
    headers = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in df.iterrows():
        row_vals = []
        for col_name in headers:
            v = row[col_name]
            if isinstance(v, float):
                row_vals.append(f"{v:.2f}")
            else:
                row_vals.append(str(v))
        lines.append("| " + " | ".join(row_vals) + " |")
    return "\n".join(lines)

def main():
    tickers = [
        "INHD", "OCC", "RNAC", "STAK", "LICN", "TNGX", "CBRL", "OFRM", "GLXY", "WNC", 
        "KLAC", "FWRD", "SNDK", "RMIX", "AIAI", "WEST", "INTC", "CAVA", "AMAT", "ARTV",
        "NRIX", "FROG", "SGML", "PWR", "TSLA", "NET", "PANW", "FLEX", "CASY", "BRKR", 
        "OPLN", "WES", "ZM"
    ]
    
    days = ["2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12"]
    
    print("Executing trader-perspective real-time Judas Swing scan...")
    
    results = []
    
    for ticker in tickers:
        try:
            # Fetch 5m data
            df = yf.download(ticker, start="2026-06-08", end="2026-06-13", interval="5m", prepost=True, progress=False)
            if df.empty:
                continue
                
            # If the DataFrame columns are MultiIndex, get cross section
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    df = df.xs(ticker, axis=1, level=1)
                except Exception as e:
                    pass
                    
            for day in days:
                res = scan_realtime_day(ticker, day, df)
                if res:
                    res['symbol'] = ticker
                    results.append(res)
                    print(f"[{day}] {ticker} confirmed Judas Swing at {res['confirm_time']} (Low established at {res['stop_hunt_time']})")
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
            
    # Print and save results
    if results:
        res_df = pd.DataFrame(results)
        disp_df = res_df[['symbol', 'date', 'open', 'stop_hunt_low', 'stop_hunt_time', 'trigger_time', 'confirm_time', 'confirm_price', 'pct_drop']]
        disp_df = disp_df.sort_values(by=['date', 'confirm_time', 'symbol'])
        
        print("\n=== REAL-TIME TRADER SCAN RESULTS ===")
        print(disp_df.to_string(index=False))
        
        md_table = to_md_table(disp_df)
        with open("scratch/realtime_judas_swings.md", "w") as f:
            f.write("# Real-Time Trader Judas Swing Detections\n\n")
            f.write(md_table)
            f.write("\n")
        print("\nSaved to scratch/realtime_judas_swings.md")
    else:
        print("No real-time Judas Swing patterns detected.")

if __name__ == "__main__":
    main()
