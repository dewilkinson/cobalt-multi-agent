import asyncio
import sys
import time

sys.path.insert(0, './')
from src.tools.smc import get_smc_analysis

async def main():
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "NFLX", "AMD", "INTC"]
    
    print("=" * 60)
    print(" SMC DATA PIPELINE PERFORMANCE BENCHMARK ")
    print("=" * 60)
    
    total_time = 0
    total_chars = 0
    
    header = f"{'Symbol':<8} | {'Latency':<10} | {'Payload Size':<12} | {'Status':<10}"
    print(header)
    print("-" * 60)
    
    for sym in symbols:
        start_time = time.perf_counter()
        try:
            res = await get_smc_analysis.coroutine(ticker=sym, period="60d", interval="1d")
            elapsed = time.perf_counter() - start_time
            
            chars = len(res)
            
            total_time += elapsed
            total_chars += chars
            
            status = "OK" if chars > 100 else "WARN"
            print(f"{sym:<8} | {elapsed:.2f}s     | {chars:<12} | [{status}]")
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            print(f"{sym:<8} | {elapsed:.2f}s     | {'ERROR':<12} | [FAIL]")
            print(f"  Error msg: {e}")
            
    print("-" * 60)
    print(f"AVERAGE LATENCY: {total_time / len(symbols):.2f}s")
    print(f"AVERAGE PAYLOAD: {total_chars / len(symbols):.0f} chars")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
