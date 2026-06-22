import yfinance as yf
import pandas as pd
import numpy as np
import pytz
from datetime import datetime

def analyze_ticker_day(ticker, day_str, df):
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
        
    # First hour of trading (09:30 to 10:30 EST)
    first_hour_df = day_df.between_time('09:30', '10:30')
    if first_hour_df.empty:
        return None
        
    # Pre-market data (04:00 to 09:29 EST)
    pre_market_df = day_df.between_time('04:00', '09:29')
    
    # 1. Open price at 09:30
    open_price = float(rth_df['Open'].iloc[0])
    
    # 2. First hour low
    hour_low = float(first_hour_df['Low'].min())
    hour_low_time = first_hour_df['Low'].idxmin()
    
    # 3. Daily low (regular trading hours)
    rth_low = float(rth_df['Low'].min())
    rth_low_time = rth_df['Low'].idxmin()
    
    # 4. Daily high (regular trading hours)
    rth_high = float(rth_df['High'].max())
    rth_high_time = rth_df['High'].idxmax()
    
    # 5. Daily close (regular trading hours)
    rth_close = float(rth_df['Close'].iloc[-1])
    
    # Check pre-market low if available
    pm_low = float(pre_market_df['Low'].min()) if not pre_market_df.empty else None
    
    # Extract scalar Timestamps from Series if necessary
    if isinstance(hour_low_time, pd.Series):
        hour_low_time = hour_low_time.iloc[0]
    if isinstance(rth_low_time, pd.Series):
        rth_low_time = rth_low_time.iloc[0]
    if isinstance(rth_high_time, pd.Series):
        rth_high_time = rth_high_time.iloc[0]
        
    is_bullish = rth_close > open_price
    low_in_first_hour = rth_low_time.time() <= datetime.strptime("10:30", "%H:%M").time()
    dipped_below_open = hour_low < open_price
    swept_premarket = (pm_low is not None) and (hour_low < pm_low)
    
    # Reversal confirmation: high is after low
    high_after_low = rth_high_time > rth_low_time
    
    # Percentage drop below open
    pct_drop_below_open = ((open_price - hour_low) / open_price) * 100
    # Daily gain
    daily_gain = ((rth_close - open_price) / open_price) * 100
    
    is_judas = is_bullish and low_in_first_hour and (dipped_below_open or swept_premarket) and high_after_low
    
    # Check that the dip was not a massive crash (should be a stop hunt, then recovery)
    # The recovery should close above the open
    if is_judas:
        return {
            'date': day_str,
            'open': open_price,
            'low': rth_low,
            'low_time': rth_low_time.strftime('%H:%M'),
            'high': rth_high,
            'high_time': rth_high_time.strftime('%H:%M'),
            'close': rth_close,
            'pct_drop': pct_drop_below_open,
            'daily_gain': daily_gain,
            'swept_premarket': swept_premarket,
            'dipped_below_open': dipped_below_open
        }
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
    
    # Download 5-minute data with pre-post market data for last week
    print("Downloading intraday 5m data for tickers...")
    
    results = []
    
    for ticker in tickers:
        print(f"Analyzing {ticker}...")
        try:
            # Fetch 5m data
            df = yf.download(ticker, start="2026-06-08", end="2026-06-13", interval="5m", prepost=True, progress=False)
            if df.empty:
                print(f"No data for {ticker}")
                continue
                
            # If the DataFrame columns are MultiIndex, get cross section
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    df = df.xs(ticker, axis=1, level=1)
                except Exception as e:
                    print(f"Could not extract single ticker columns for {ticker}: {e}")
                    
            for day in days:
                res = analyze_ticker_day(ticker, day, df)
                if res:
                    res['symbol'] = ticker
                    results.append(res)
                    print(f"  -> FOUND Judas Swing on {day}: Open={res['open']:.2f}, Low={res['low']:.2f} at {res['low_time']}, Close={res['close']:.2f} (+{res['daily_gain']:.2f}%)")
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            import traceback
            traceback.print_exc()
            
    # Print final results
    if results:
        res_df = pd.DataFrame(results)
        # Select columns to display
        disp_df = res_df[['symbol', 'date', 'open', 'low', 'low_time', 'high', 'high_time', 'close', 'pct_drop', 'daily_gain']]
        disp_df = disp_df.sort_values(by=['date', 'symbol'])
        print("\n=== JUDAS SWING SCAN RESULTS ===")
        print(disp_df.to_string(index=False))
        
        # Save to markdown format
        md_table = to_md_table(disp_df)
        with open("scratch/judas_swings.md", "w") as f:
            f.write("# Judas Swing Scan Results\n\n")
            f.write(md_table)
            f.write("\n")
        print("\nResults saved to scratch/judas_swings.md")
    else:
        print("\nNo Judas Swing patterns detected.")

if __name__ == "__main__":
    main()
