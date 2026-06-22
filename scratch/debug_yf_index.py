import yfinance as yf
import pandas as pd

def debug():
    tickers = ["SPY", "QQQ", "IWM", "DX-Y.NYB", "^VIX", "^TNX", "CL=F", "BTC-USD"]
    df = yf.download(
        tickers=tickers,
        period="5d",
        interval="1h",
        group_by="ticker",
        progress=False,
        threads=False,
        timeout=20.0,
        auto_adjust=False,
        prepost=True,
    )
    print("Raw DataFrame Index Type:", type(df.index))
    print("Is index sorted?", df.index.is_monotonic_increasing)
    
    # Print index values
    print("DataFrame Index Tail 15:")
    print(df.index[-15:])
    
    # Try extracting QQQ Close
    qqq_close = df[("QQQ", "Close")].dropna()
    print("QQQ Close Index Tail 15:")
    print(qqq_close.tail(15))
    
    print("Is QQQ Close index sorted?", qqq_close.index.is_monotonic_increasing)

if __name__ == "__main__":
    debug()
