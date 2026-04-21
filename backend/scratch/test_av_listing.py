import os
import httpx
import pandas as pd
from io import StringIO

def test_listing_status():
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "demo")
    url = f"https://www.alphavantage.co/query?function=LISTING_STATUS&apikey={api_key}"
    
    print(f"Fetching listing status from {url.replace(api_key, 'REDACTED')}...")
    try:
        resp = httpx.get(url, timeout=30.0)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        print(f"Total active listings: {len(df)}")
        print(df.head())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_listing_status()
