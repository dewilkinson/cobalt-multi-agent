# Specialized SMC Performance Benchmark
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import time
import os
import sys
import logging
from datetime import datetime

# Setup path and env
sys.path.insert(0, './')
os.environ["COBALT_AI_ON"] = "True"
os.environ["VLI_DEBUG_MODE"] = "True" # Auto-approve plans

# Suppress noisy logs
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("SMCBenchmark")

from src.server.app import _invoke_vli_agent
from src.services.datastore import DatastoreManager

async def run_benchmark_set(name, vli_llm_type, symbols):
    print(f"\n{'='*60}")
    print(f" STARTING BENCHMARK SET: {name}")
    print(f" LLM TYPE: {vli_llm_type}")
    print(f"{'='*60}")
    
    results = []
    for sym in symbols:
        # 1. Total Cache Invalidation (Uncached fetch requirement)
        DatastoreManager.get_history_cache().clear()
        
        print(f"[BENCH] {sym:<6} | Model: {vli_llm_type:<10} | Routine: SMC Analysis...", end=" ", flush=True)
        
        start_time = time.perf_counter()
        directive = f"Run a full SMC analysis for {sym}. Provide a verbose institutional grade report."
        
        try:
            # We use raw_data_mode=False for full synthesis as requested
            res = await asyncio.wait_for(
                _invoke_vli_agent(
                    text=directive, 
                    vli_llm_type=vli_llm_type,
                    raw_data_mode=False
                ), 
                timeout=180.0
            )
            duration = time.perf_counter() - start_time
            print(f"PASS | Duration: {duration:.2f}s")
            results.append({"symbol": sym, "duration": duration, "status": "PASS"})
        except asyncio.TimeoutError:
            duration = time.perf_counter() - start_time
            print(f"FAIL | Timeout after {duration:.2f}s")
            results.append({"symbol": sym, "duration": duration, "status": "TIMEOUT"})
        except Exception as e:
            duration = time.perf_counter() - start_time
            print(f"FAIL | Error: {str(e)[:50]}")
            results.append({"symbol": sym, "duration": duration, "status": "ERROR"})
            
        # Cooldown between requests to avoid rate limiting
        await asyncio.sleep(2)
        
    return results

async def main():
    symbols = ["NVDA", "AAPL", "MSFT", "TSLA", "AMD"]
    
    # Run Set 1: Gemma 4 (Core)
    gemma_results = await run_benchmark_set("Gemma 4 (Local Core)", "core", symbols)
    
    # Run Set 2: Gemini 3 Pro Low (Reasoning/High Reasoning)
    gemini_results = await run_benchmark_set("Gemini 3 Pro Low", "reasoning", symbols)
    
    # Final Comparison Table
    print("\n\n" + "="*85)
    print("SMC PERFORMANCE REPORT: ORCHESTRATOR SYNTHESIS COMPARISON".center(85))
    print("="*85)
    header = f"{'Symbol':<10} | {'Gemma 4 (s)':<15} | {'Gemini 3 Pro (s)':<15} | {'Delta (s)':<15}"
    print(header)
    print("-" * 85)
    
    gemma_total = 0
    gemini_total = 0
    valid_count = 0
    
    for i in range(len(symbols)):
        g = gemma_results[i]
        gem = gemini_results[i]
        
        g_dur = g['duration']
        gem_dur = gem['duration']
        delta = g_dur - gem_dur
        
        g_str = f"{g_dur:.2f}s" if g['status'] == "PASS" else g['status']
        gem_str = f"{gem_dur:.2f}s" if gem['status'] == "PASS" else gem['status']
        delta_str = f"{delta:+.2f}s" if g['status'] == "PASS" and gem['status'] == "PASS" else "N/A"
        
        print(f"{symbols[i]:<10} | {g_str:<15} | {gem_str:<15} | {delta_str:<15}")
        
        if g['status'] == "PASS" and gem['status'] == "PASS":
            gemma_total += g_dur
            gemini_total += gem_dur
            valid_count += 1
            
    print("-" * 85)
    if valid_count > 0:
        avg_g = gemma_total / valid_count
        avg_gem = gemini_total / valid_count
        print(f"{'AVERAGE':<10} | {avg_g:<15.2f} | {avg_gem:<15.2f} | {avg_g - avg_gem:+.2f}s")
        speedup = (avg_gem / avg_g - 1) * 100 if avg_g > 0 else 0
        print(f"\nRelative Speed Comparison: {'Gemma 4' if avg_g < avg_gem else 'Gemini 3 Pro'} is {abs(speedup):.1f}% faster on average.")
    print("=" * 85)

if __name__ == "__main__":
    asyncio.run(main())
