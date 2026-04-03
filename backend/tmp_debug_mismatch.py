import yfinance as yf
import pandas as pd

def _extract_ticker_data(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    ticker_upper = ticker.upper()
    if isinstance(df.columns, pd.MultiIndex):
        if ticker_upper in df.columns.levels[0]:
            print(f"DEBUG: Found {ticker_upper} in levels[0]")
            return df[ticker_upper].dropna(how='all')
        else:
            print(f"DEBUG: {ticker_upper} NOT in levels[0]. Levels are: {df.columns.levels[0]}")
    return df.dropna(how='all')

def debug_batch():
    # Simulate what _fetch_batch_history does
    original_tickers = ["VIX"]
    mapped_tickers = ["^VIX" if t == "VIX" else t for t in original_tickers]
    
    print(f"DEBUG: Downloading mapped {mapped_tickers}...")
    df = yf.download(tickers=mapped_tickers, period="1d", group_by='ticker', progress=False)
    
    print("DEBUG: Columns structure:")
    print(df.columns)
    
    # Simulate Scout extracting data for "VIX"
    print("\nDEBUG: Attempting to extract 'VIX' from the result...")
    extracted = _extract_ticker_data(df, "VIX")
    print("DEBUG: Extracted head:")
    print(extracted.head())
    
    if "Close" not in extracted.columns:
        print("DEBUG: FAILURE - Extracted DF does not have 'Close' column at top level.")

if __name__ == "__main__":
    debug_batch()
