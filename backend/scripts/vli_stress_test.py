
import asyncio
import os
import sys
import time
import json
import logging
from datetime import datetime
from statistics import mean, median

# Ensure backend is in path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from src.tools.finance import get_stock_quote
from src.utils.vli_metrics import log_vli_metric
from src.server.app import _invoke_vli_agent

# Configure logging to be quiet for the stress test
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("vli_stress")

async def run_single_ticker_benchmark(ticker: str, iterations: int = 10):
    print(f"\n--- [Phase 1] Single Ticker Benchmarking: {ticker} ({iterations} iterations) ---")
    latencies = []
    success_count = 0
    
    for i in range(iterations):
        start = time.time()
        try:
            # [FIX] Use underlying function for StructuredTool
            q_func = getattr(get_stock_quote, 'coroutine', getattr(get_stock_quote, 'func', None))
            res = await q_func(ticker=ticker, use_fast_path=True)
            duration = time.time() - start
            latencies.append(duration)
            
            status = "pass" if isinstance(res, dict) and "price" in res else "fail"
            if status == "pass": success_count += 1
            
            # Log to persistent store
            log_vli_metric(f"stress_single_{ticker}", duration, iteration=i+1, is_stress_test=True, status=status)
            print(f"  Iteration {i+1:2}: {duration:.3f}s | Status: {status}")
        except Exception as e:
            print(f"  Iteration {i+1:2}: FAILED ({e})")
            log_vli_metric(f"stress_single_{ticker}", 0, iteration=i+1, is_stress_test=True, status="error")
            
    _print_stats(latencies, success_count, iterations)

async def run_macro_batch_benchmark(iterations: int = 5):
    print(f"\n--- [Phase 2] Macro Batch Benchmarking (5 tickers, {iterations} iterations) ---")
    latencies = []
    success_count = 0
    
    # We use the _invoke_vli_agent with the specific command to test the app-level Fast-Path
    command = "Get Macro stock list PRICE"
    
    for i in range(iterations):
        start = time.time()
        try:
            res = await _invoke_vli_agent(command)
            duration = time.time() - start
            latencies.append(duration)
            
            # Check if it returned the expected format
            status = "pass" if "Atomic Fast-Path" in res else "fail"
            if status == "pass": success_count += 1
            
            log_vli_metric("stress_macro_batch", duration, iteration=i+1, is_stress_test=True, status=status)
            print(f"  Iteration {i+1:2}: {duration:.3f}s | Status: {status}")
        except Exception as e:
            print(f"  Iteration {i+1:2}: FAILED ({e})")
            log_vli_metric("stress_macro_batch", 0, iteration=i+1, is_stress_test=True, status="error")
            
    _print_stats(latencies, success_count, iterations)

async def run_concurrency_stress(concurrency: int = 5):
    print(f"\n--- [Phase 3] Concurrency Stress (Parallel Burst: {concurrency} workers) ---")
    
    async def worker(wid):
        start = time.time()
        q_func = getattr(get_stock_quote, 'coroutine', getattr(get_stock_quote, 'func', None))
        await q_func(ticker="VIX", use_fast_path=True)
        return time.time() - start

    start_burst = time.time()
    tasks = [worker(i) for i in range(concurrency)]
    results = await asyncio.gather(*tasks)
    total_duration = time.time() - start_burst
    
    print(f"  Burst completed in {total_duration:.3f}s")
    for i, lat in enumerate(results):
        print(f"    Worker {i+1}: {lat:.3f}s")
    
    avg_lat = mean(results)
    print(f"  Average Worker Latency: {avg_lat:.3f}s")

def _print_stats(latencies, success_count, total):
    if not latencies: return
    avg = mean(latencies)
    p95 = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]
    print(f"\n  Final Results:")
    print(f"    Total Success: {success_count}/{total} ({(success_count/total)*100:.1f}%)")
    print(f"    Min Latency:   {min(latencies):.3f}s")
    print(f"    Max Latency:   {max(latencies):.3f}s")
    print(f"    Avg Latency:   {avg:.3f}s")
    print(f"    P95 Latency:   {p95:.3f}s")

async def main():
    print(f"VLI DASHBOARD STRESS TEST - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # 1. Sequential Single Ticker
    await run_single_ticker_benchmark("VIX", iterations=10)
    
    # 2. Sequential Macro Batch
    await run_macro_batch_benchmark(iterations=5)
    
    # 3. Parallel Burst
    await run_concurrency_stress(concurrency=5)
    
    print("\n" + "="*60)
    print("Stress Test Completed. Results persisted to logs/vli_performance.jsonl")

if __name__ == "__main__":
    asyncio.run(main())
