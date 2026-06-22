import sqlite3
import yfinance as yf
import pandas as pd
import numpy as np

def main():
    # 1. Connect to database and get unique tickers
    conn = sqlite3.connect('backend/data/vli_main.db')
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ticker FROM persistent_cache;")
    db_tickers = [row[0] for row in cursor.fetchall() if row[0] and row[0].isalnum()]
    conn.close()
    
    print(f"Retrieved {len(db_tickers)} unique tickers from database.")
    
    # 2. Add some known tickers from web search and standard leaders
    web_tickers = ["SPCX", "CASY", "FSLR", "PWR", "TSLA", "INHD", "STAK", "STI", "INDP", "MRVL", "FLEX", "NRIX", "SPY", "QQQ"]
    all_tickers = list(set(db_tickers + web_tickers))
    
    # Clean ticker symbols
    all_tickers = [t.strip().upper() for t in all_tickers if len(t.strip()) <= 5]
    print(f"Total tickers to fetch: {len(all_tickers)}")
    
    # 3. Batch fetch historical data from June 5 to June 13, 2026
    start_date = "2026-06-05"
    end_date = "2026-06-13"
    
    print(f"Downloading historical data from {start_date} to {end_date}...")
    try:
        df = yf.download(all_tickers, start=start_date, end=end_date, group_by='ticker', progress=False)
    except Exception as e:
        print(f"Error downloading batch: {e}")
        return
        
    results = []
    
    for ticker in all_tickers:
        try:
            # Handle yfinance single ticker vs multi-ticker DataFrame format
            if len(all_tickers) == 1:
                ticker_df = df
            else:
                ticker_df = df[ticker]
                
            ticker_df = ticker_df.dropna(subset=['Close'])
            if ticker_df.empty or len(ticker_df) < 2:
                continue
                
            # We want the return from June 5 Close (or first available day's Close) to June 12 Close
            # Let's sort index just in case
            ticker_df = ticker_df.sort_index()
            
            p_start = ticker_df['Close'].iloc[0]
            p_end = ticker_df['Close'].iloc[-1]
            
            # Dates
            d_start = ticker_df.index[0].strftime('%Y-%m-%d')
            d_end = ticker_df.index[-1].strftime('%Y-%m-%d')
            
            if p_start > 0:
                pct_change = ((p_end - p_start) / p_start) * 100
                results.append({
                    'symbol': ticker,
                    'start_date': d_start,
                    'start_price': p_start,
                    'end_date': d_end,
                    'end_price': p_end,
                    'pct_change': pct_change
                })
        except Exception as e:
            # Ticker might not exist in yfinance or download failed
            continue
            
    # 4. Sort and display top performers
    res_df = pd.DataFrame(results)
    if res_df.empty:
        print("No returns data found.")
        return
        
    res_df = res_df.sort_values(by='pct_change', ascending=False)
    
    print("\n--- TOP PERFORMING STOCKS OF THE WEEK (June 8 - June 12, 2026) ---")
    print(res_df.head(20).to_string(index=False))

if __name__ == "__main__":
    main()
