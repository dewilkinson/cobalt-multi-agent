import asyncio
import logging
import sys
import os

# Set up logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.append(os.getcwd())

from src.tools.finance import get_stock_quote, run_smc_analysis
from src.tools.scraper import get_latest_ux_data

async def test_nee():
    ticker = "NEE"
    print(f"Testing analysis for {ticker}...")
    
    try:
        print("1. Fetching Quote...")
        quote = await get_stock_quote.ainvoke({"ticker": ticker})
        print(f"Quote: {quote}")
        
        print("\n2. Running SMC Analysis...")
        smc = await run_smc_analysis.ainvoke({"ticker": ticker, "interval": "1d"})
        print(f"SMC Analysis snippet: {str(smc)[:500]}...")
        
    except Exception as e:
        print(f"ERROR during {ticker} analysis: {e}")

if __name__ == "__main__":
    asyncio.run(test_nee())
