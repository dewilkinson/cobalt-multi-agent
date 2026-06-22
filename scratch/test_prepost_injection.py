import asyncio
import os
import sys
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

# Force logging to console
import logging
logging.basicConfig(level=logging.INFO)

from src.tools.finance import _fetch_stock_history, _get_active_prepost_price

def test_prepost():
    print("Testing pre/post price injection for HPE:")
    # Fetch active prepost price from yfinance directly to see what it is
    quote = _get_active_prepost_price("HPE")
    print(f"Direct pre/post quote: {quote}")

    # Fetch stock history using our patched function
    df = _fetch_stock_history("HPE", period="5d", interval="1d")
    print("\nDataFrame tail:")
    print(df.tail())
    
    if quote:
        last_price = df.iloc[-1]["Close"]
        print(f"\nLast price in DataFrame: {last_price}")
        print(f"Expected price from quote: {quote['price']}")
        if abs(last_price - quote['price']) < 0.001:
            print("SUCCESS: Pre/post price is correctly injected!")
        else:
            print("FAILURE: Pre/post price is NOT injected or mismatched.")
    else:
        print("WARNING: Could not fetch active pre/post price. Maybe market is closed and no pre/post quotes are available, or yfinance failed.")

if __name__ == "__main__":
    test_prepost()
