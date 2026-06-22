import yfinance as yf
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, time

def analyze_hybrid_day(ticker, day_str, df_1m, df_5m):
    # Localize to US/Eastern timezone
    est = pytz.timezone('America/New_York')
    
    # Process 5m first to see if there's a macro structure
    day_5m = df_5m[df_5m.index.strftime('%Y-%m-%d') == day_str]
    day_1m = df_1m[df_1m.index.strftime('%Y-%m-%d') == day_str]
    
    if day_5m.empty or day_1m.empty:
        return None
        
    day_5m = day_5m.tz_convert(est)
    day_1m = day_1m.tz_convert(est)
    
    rth_5m = day_5m.between_time('09:30', '16:00')
    rth_1m = day_1m.between_time('09:30', '16:00')
    
    if rth_5m.empty or rth_1m.empty:
        return None
        
    # Open price at 09:30 AM
    open_price = float(rth_5m['Open'].iloc[0])
    
    # We will step through the 1-minute bars sequentially starting at 09:30 AM
    stop_hunt_low = None
    stop_hunt_time = None
    state = "LOOKING_FOR_DIP"
    trigger_time = None
    confirm_count = 0
    
    cutoff_first_hour = time(10, 30)
    
    # We trace minute by minute
    for idx in range(len(rth_1m)):
        row = rth_1m.iloc[idx]
        t = rth_1m.index[idx]
        t_time = t.time()
        
        low_val = float(row['Low'])
        close_val = float(row['Close'])
        
        # 1. State: Looking for initial stop hunt drop below the open in the first hour
        if t_time <= cutoff_first_hour:
            if low_val < open_price:
                if stop_hunt_low is None or low_val < stop_hunt_low:
                    stop_hunt_low = low_val
                    stop_hunt_time = t
                    state = "LOOKING_FOR_REVERSAL"
                    confirm_count = 0
                    
        # 2. State: Looking for reversal back above the open
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
                
                # Check if close is above open to trigger (on 1-minute chart)
                if close_val > open_price:
                    trigger_time = t
                    state = "CONFIRMING"
                    confirm_count = 0
                    
        # 3. State: Confirming the breakout (needs 3 consecutive 1m bars holding above open)
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
                if confirm_count == 3: # 3 consecutive minutes of confirmation on 1m chart
                    # Now let's check the 5-minute chart for alignment.
                    # Find the corresponding 5m candle close time that covers this confirm_time
                    confirm_5m = rth_5m[rth_5m.index >= t]
                    if not confirm_5m.empty:
                        confirm_5m_time = confirm_5m.index[0]
                        confirm_5m_price = float(confirm_5m['Close'].iloc[0])
                    else:
                        confirm_5m_time = t
                        confirm_5m_price = close_val
                        
                    pct_drop = ((open_price - stop_hunt_low) / open_price) * 100
                    return {
                        'date': day_str,
                        'open': open_price,
                        'stop_hunt_low': stop_hunt_low,
                        'stop_hunt_time': stop_hunt_time.strftime('%H:%M'),
                        'trigger_time_1m': trigger_time.strftime('%H:%M'),
                        'confirm_time_1m': t.strftime('%H:%M'),
                        'confirm_price_1m': close_val,
                        'confirm_time_5m': confirm_5m_time.strftime('%H:%M'),
                        'confirm_price_5m': confirm_5m_price,
                        'pct_drop': pct_drop
                    }
            else:
                # Closed below open during confirmation, reset
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
    
    print("Executing hybrid 1m/5m sequential real-time Judas Swing scan...")
    
    results = []
    
    for ticker in tickers:
        print(f"Fetching data for {ticker}...")
        try:
            # Download 1-minute data for last week
            df_1m = yf.download(ticker, start="2026-06-08", end="2026-06-13", interval="1m", prepost=True, progress=False)
            if df_1m.empty:
                print(f"  No 1m data for {ticker}")
                continue
                
            # Download 5-minute data
            df_5m = yf.download(ticker, start="2026-06-08", end="2026-06-13", interval="5m", prepost=True, progress=False)
            if df_5m.empty:
                print(f"  No 5m data for {ticker}")
                continue
                
            # Handle MultiIndex
            if isinstance(df_1m.columns, pd.MultiIndex):
                df_1m = df_1m.xs(ticker, axis=1, level=1)
            if isinstance(df_5m.columns, pd.MultiIndex):
                df_5m = df_5m.xs(ticker, axis=1, level=1)
                
            for day in days:
                res = analyze_hybrid_day(ticker, day, df_1m, df_5m)
                if res:
                    res['symbol'] = ticker
                    results.append(res)
                    print(f"  [{day}] {ticker} CONFIRMED Judas Swing at 1m:{res['confirm_time_1m']} / 5m:{res['confirm_time_5m']} (Low established at {res['stop_hunt_time']})")
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
            import traceback
            traceback.print_exc()
            
    # Print and save results
    if results:
        res_df = pd.DataFrame(results)
        disp_df = res_df[['symbol', 'date', 'open', 'stop_hunt_low', 'stop_hunt_time', 'trigger_time_1m', 'confirm_time_1m', 'confirm_time_5m', 'confirm_price_5m', 'pct_drop']]
        disp_df = disp_df.sort_values(by=['date', 'confirm_time_1m', 'symbol'])
        
        print("\n=== HYBRID REAL-TIME SCAN RESULTS ===")
        print(disp_df.to_string(index=False))
        
        md_table = to_md_table(disp_df)
        with open("scratch/hybrid_judas_swings.md", "w") as f:
            f.write("# Hybrid 1m/5m Real-Time Judas Swing Detections\n\n")
            f.write(md_table)
            f.write("\n")
        print("\nSaved to scratch/hybrid_judas_swings.md")
    else:
        print("\nNo Judas Swing patterns detected in hybrid scan.")

if __name__ == "__main__":
    main()
