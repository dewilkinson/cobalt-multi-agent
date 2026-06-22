import asyncio
import os
import sys
import yfinance as yf
import pandas as pd

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from src.tools.finance import _fetch_batch_history, _extract_ticker_data

def test():
    tickers = ["SPY", "QQQ", "IWM", "DX-Y.NYB", "^VIX", "^TNX", "CL=F", "BTC-USD"]
    df = _fetch_batch_history(tickers, "5d", "1h")
    print("DataFrame Columns levels:", df.columns.levels if isinstance(df.columns, pd.MultiIndex) else "Flat")
    
    qqq_df = _extract_ticker_data(df, "QQQ")
    print("QQQ DataFrame index and Close column (tail 15):")
    print(qqq_df["Close"].tail(15))
    
    print("\nIs index monotonic increasing?", qqq_df.index.is_monotonic_increasing)

if __name__ == "__main__":
    test()
