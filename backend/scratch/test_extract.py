import pandas as pd
import yfinance as yf
from src.tools.finance import _extract_ticker_data

def run():
    tickers = ["SPY", "QQQ", "IWM", "DX-Y.NYB", "^VIX", "^TNX", "CL=F", "BTC-USD"]
    df = yf.download(tickers, period="5d", interval="1d", group_by="ticker")
    print(f"Index type: {type(df.columns)}")
    for t in tickers:
        extracted = _extract_ticker_data(df, t)
        print(f"{t}: empty? {extracted.empty}")
        if extracted.empty:
            print("Why it's empty:", df.get(t.upper()), df.xs(t.upper(), level=0, axis=1) if isinstance(df.columns, pd.MultiIndex) else None)

if __name__ == "__main__":
    run()
