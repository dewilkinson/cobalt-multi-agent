import yfinance as yf
import pandas as pd
from datetime import datetime

def check_qqq():
    print("=== QQQ Daily Data ===")
    daily = yf.download("QQQ", period="5d", interval="1d")
    print(daily)
    
    print("\n=== QQQ Intraday 1h Data ===")
    hourly = yf.download("QQQ", period="5d", interval="1h")
    print(hourly.tail(15))
    
    print("\n=== QQQ Intraday 1m Data ===")
    m1 = yf.download("QQQ", period="2d", interval="1m")
    print(m1.tail(15))

if __name__ == "__main__":
    check_qqq()
