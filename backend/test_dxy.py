import logging

import yfinance as yf

logging.basicConfig(level=logging.INFO)

tickers = ["DX-Y.NYB", "DX=F", "DXY", "USD=X"]

for t in tickers:
    print(f"Testing {t}...")
    try:
        data = yf.Ticker(t).history(period="1d")
        if not data.empty:
            print(f"  SUCCESS: {t} Close: {data['Close'].iloc[-1]}")
        else:
            print(f"  FAILED: {t} No data")
    except Exception as e:
        print(f"  ERROR: {t} {e}")
