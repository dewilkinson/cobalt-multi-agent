import asyncio
import logging
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tools.scanner import batch_fetch_sortino

async def test():
    tickers = ["AAPL", "TSLA", "MSFT", "invalid_ticker_xyz"]
    print(f"Testing batch_fetch_sortino for {tickers}...")
    results = await batch_fetch_sortino(tickers)
    print("Results:")
    for t, s in results.items():
        print(f"  {t}: {s}")

if __name__ == "__main__":
    asyncio.run(test())
