import asyncio
import time
import sys
import os

# Append backend to path for importing src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tools.finance import run_smc_analysis

async def main():
    print("Starting SMC analysis test for IRDM...")
    start_time = time.time()
    
    # Try to invoke the original coroutine
    try:
        if hasattr(run_smc_analysis, "coroutine"):
            result = await run_smc_analysis.coroutine(ticker="IRDM", interval="auto")
        elif hasattr(run_smc_analysis, "func"):
            result = await run_smc_analysis.func(ticker="IRDM", interval="auto")
        else:
            result = await run_smc_analysis.ainvoke({"ticker": "IRDM", "interval": "auto"})
            
        duration = time.time() - start_time
        print(f"\n--- ANALYSIS COMPLETED IN {duration:.2f} SECONDS ---\n")
        print("Result Snippet (first 500 chars):")
        print(str(result)[:500])
        
    except Exception as e:
        duration = time.time() - start_time
        print(f"\n--- HANG/ERROR AFTER {duration:.2f} SECONDS ---\n")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
