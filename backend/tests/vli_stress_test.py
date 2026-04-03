import argparse
import time
import json
import os
import requests
from datetime import datetime

# 100 Real Stock Symbols
REAL_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "UNH", "JNJ",
    "JPM", "V", "PG", "MA", "HD", "CVX", "ABBV", "LLY", "MRK", "PEP",
    "COST", "KO", "AVGO", "TMO", "WMT", "MCD", "CSCO", "ABT", "DHR", "ACN",
    "DIS", "PFE", "NFLX", "LIN", "ADBE", "TXN", "CMCSA", "AMD", "PM", "VZ",
    "NKE", "NEE", "INTC", "QCOM", "RTX", "HON", "UNP", "LOW", "SPGI", "IBM",
    "AMAT", "BA", "GE", "SYK", "ELV", "GS", "INTU", "COP", "NOW", "PLD",
    "SBUX", "ISRG", "BLK", "MDLZ", "T", "MDT", "CB", "TJX", "C", "GILD",
    "AXP", "ADI", "LMT", "VRTX", "SYY", "CVS", "ZTS", "CI", "BDX", "REGN",
    "SLB", "PGR", "MMC", "TGT", "EOG", "BSX", "SO", "CME", "AON", "NOC",
    "ITW", "WM", "CSX", "EQIX", "DUK", "APD", "ICE", "KMB", "SHW", "CL"
]

def run_chunk(chunk_index: int):
    start_idx = chunk_index * 10
    end_idx = start_idx + 10
    if start_idx >= len(REAL_SYMBOLS):
        print(f"Chunk {chunk_index} out of bounds.")
        return

    chunk_symbols = REAL_SYMBOLS[start_idx:end_idx]
    print(f"=== Running Chunk {chunk_index} ({start_idx} to {end_idx - 1}) ===")

    # 1. Generate standard prompts for each case
    # Case 0: Fast fetch (0)
    # Case 1: Batch fetch (1)
    # Case 2: Fast fetch (2)
    # Case 3: Cache hit test on (0)
    # Case 4: Refresh fetch on (2)
    # Case 5: Finviz fallback on (5)
    # Case 6: Image Scanner on (6)
    # Case 7: Batch fetch on (7) and (8)
    # Case 8: Invalidate entire cache and fetch (9)
    # Case 9: Fast fetch on (4)

    tasks = [
        {"desc": "Fast fetch", "prompt": f"Get the current price for {chunk_symbols[0]}"},
        {"desc": "Batch fetch", "prompt": f"Get the price for {chunk_symbols[1]} but explicitly set the get_stock_quote parameter use_fast_path to False"},
        {"desc": "Fast fetch", "prompt": f"Get the current price for {chunk_symbols[2]}"},
        {"desc": "Cache hit check", "prompt": f"Get the current price for {chunk_symbols[0]} again"},
        {"desc": "Refresh check", "prompt": f"Get a fresh, updated price for {chunk_symbols[2]}"},
        {"desc": "Finviz text fallback", "prompt": f"Get the price for {chunk_symbols[5]} using the explicit finviz fallback (set use_finviz_fallback to True)"},
        {"desc": "Image scanner", "prompt": f"Capture a snapshot of the chart for {chunk_symbols[6]} using the snapper tool"},
        {"desc": "Batch multi-fetch", "prompt": f"Get the price for {chunk_symbols[7]} and {chunk_symbols[8]} explicitly setting use_fast_path to False for both"},
        {"desc": "Global Inv & Fetch", "prompt": f"Invalidate the entire market cache using invalidate_market_cache, then get the price for {chunk_symbols[9]}"},
        {"desc": "Fast fetch", "prompt": f"Get the current price for {chunk_symbols[4]}"}
    ]

    results = []

    for i, task in enumerate(tasks):
        print(f"\n[Task {i}] {task['desc']}...")
        print(f"  Prompt: {task['prompt']}")
        
        start_time = time.time()
        
        try:
            resp = requests.post(
                "http://127.0.0.1:8000/api/vli/action-plan", 
                json={"text": task['prompt'], "is_action_plan": False},
                timeout=120 # generous timeout for LLM
            )
            resp.raise_for_status()
            elapsed_ms = (time.time() - start_time) * 1000
            data = resp.json()
            response_text = data.get("response", "No response text")
            print(f"  => SUCCESS ({elapsed_ms:.1f}ms)")
            
            results.append({
                "task_index": i,
                "desc": task['desc'],
                "prompt": task['prompt'],
                "latency_ms": elapsed_ms,
                "status": "Success",
                "notes": response_text[:100].replace('\n', ' ') + "..."
            })
        except Exception as e:
            import sys
            elapsed_ms = (time.time() - start_time) * 1000
            print(f"  => CRITICAL FAILURE ({elapsed_ms:.1f}ms): {e}")
            results.append({
                "task_index": i,
                "desc": task['desc'],
                "prompt": task['prompt'],
                "latency_ms": elapsed_ms,
                "status": "Failed",
                "notes": str(e)
            })
            export_report(chunk_index, results)
            print(f"\n[FATAL] Test aborted at Task {i} due to failure.")
            sys.exit(1)
            
        # Fixed 3s delay between tasks for high-speed stress testing
        if i < len(tasks) - 1:
            print(f"  [Waiting 3.0s for next task...]")
            time.sleep(3.0)

    # Export report to Obsidian Inbox on full pass
    export_report(chunk_index, results)


def export_report(chunk_index, results):
    inbox_dir = r"C:\github\obsidian-vault\_cobalt\inbox"
    os.makedirs(inbox_dir, exist_ok=True)
    report_file = os.path.join(inbox_dir, f"stress_test_report_chunk_{chunk_index}.md")

    md_lines = [
        f"# VLI Stress Test Report - Chunk {chunk_index}",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| Task | Description | Prompt | Latency (ms) | Status | Notes |",
        "|---|---|---|---|---|---|"
    ]

    for r in results:
        md_lines.append(f"| {r['task_index']} | {r['desc']} | `{r['prompt']}` | {r['latency_ms']:.1f} | {r['status']} | {r['notes']} |")

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # Also save as JSON for the separate latency analysis test
    log_dir = r"c:\github\cobalt-multi-agent\backend\logs"
    os.makedirs(log_dir, exist_ok=True)
    json_file = os.path.join(log_dir, f"stress_test_report_chunk_{chunk_index}.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    print(f"\nReport written to: {report_file}")
    print(f"Data saved to: {json_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VLI Stress Test Harness")
    parser.add_argument("--chunk", type=int, default=0, help="Chunk index (0-9) to run")
    args = parser.parse_args()
    
    run_chunk(args.chunk)
