import asyncio
import sys
import os
import traceback

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from src.tools.finance import run_smc_analysis

async def debug_smc():
    ticker = "BTC-USD"
    interval = "1h"
    print(f"--- Debugging SMC Technical Research: {ticker} @ {interval} ---")
    
    # We want the RAW function to see the error
    func = run_smc_analysis.coroutine if hasattr(run_smc_analysis, 'coroutine') else run_smc_analysis
    
    try:
        result = await func(ticker, interval)
        print("\nTool Result:")
        print(result)
        
        if "[ERROR]" in result:
             print("\n[CONFIRMED] Tool returned an error string.")

    except Exception:
        print("\n[CRITICAL] Function raised an exception:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_smc())
