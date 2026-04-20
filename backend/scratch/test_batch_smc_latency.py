import asyncio
import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tools.smc import get_batch_smc_analysis

async def run_latency_test():
    tickers = "SPY, QQQ, AAPL, MSFT, TSLA, NVDA, GOOGL, META, AMZN, NFLX"
    print(f"Testing batch_smc latency for 10 tickers: {tickers}")
    
    start_time = time.time()
    
    # Execute batch_smc_analysis
    try:
        result = await get_batch_smc_analysis.ainvoke({"tickers_list": tickers})
        end_time = time.time()
        
        latency = end_time - start_time
        print(f"\n=======================")
        print(f"BATCH SMC SWEEP COMPLETE")
        print(f"=======================\n")
        print(f"Total Latency: {latency:.2f} seconds")
        print(f"Average time per ticker (with Semaphore=3): {(latency/10):.2f} seconds")
        print(f"Report Length Generated: {len(result)} characters")
        
    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_latency_test())
