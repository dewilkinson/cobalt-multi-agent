import asyncio
import os
import sys
import pandas as pd
import time
from unittest.mock import MagicMock, patch
from datetime import datetime

# Set PYTHONPATH to include the current directory for imports
sys.path.append(os.getcwd())

from src.tools.finance import get_stock_quote, _normalize_ticker, _extract_ticker_data

async def run_diagnostics():
    print(f"--- SCOUT RESONANCE DIAGNOSTICS ---")
    print(f"Started at {datetime.now().strftime('%H:%M:%S')}\n")
    
    results = {"pass": 0, "fail": 0}

    # 1. Normalization Check
    print("[1] SYMBOL NORMALIZATION")
    tests = [("VIX", "^VIX"), ("SPX", "^GSPC"), ("DXY", "DX-Y.NYB"), ("TNX", "^TNX"), ("AAPL", "AAPL")]
    for sym, expected in tests:
        actual = _normalize_ticker(sym)
        if actual == expected:
            print(f"  OK: {sym} -> {actual}")
            results["pass"] += 1
        else:
            print(f"  FAIL: {sym} -> {actual} (Expected: {expected})")
            results["fail"] += 1
    
    # 2. MultiIndex Alignment Check
    print("\n[2] MULTI-INDEX ALIGNMENT")
    try:
        cols = pd.MultiIndex.from_tuples([('^VIX', 'Close'), ('^VIX', 'High')])
        df = pd.DataFrame([{"Close": 30.75, "High": 31.0}], index=[pd.Timestamp.now()])
        df.columns = cols
        
        extracted = _extract_ticker_data(df, "VIX")
        if not extracted.empty and extracted.iloc[0]['Close'] == 30.75:
            print(f"  OK: Successfully aligned 'VIX' with '^VIX' in MultiIndex.")
            results["pass"] += 1
        else:
            print(f"  FAIL: Could not extract 'VIX' from mapped '^VIX' data.")
            results["fail"] += 1
    except Exception as e:
        print(f"  ERROR: {e}")
        results["fail"] += 1

    # 3. Fallback Trigger Check
    print("\n[3] VISIONARY FALLBACK TRIGGER")
    # Simulate yfinance failure
    with patch("src.tools.finance._fetch_batch_history") as mock_fetch:
        mock_fetch.side_effect = Exception("CON_ERROR: 403 Forbidden")
        
        # Mock snapper to return a fake visual response
        with patch("src.tools.screenshot.snapper.func") as mock_snap:
            mock_snap.return_value = '{"images": ["data:image/png;base64,..."], "source": "TV"}'
            
            print("  Simulating yfinance failure for 'VIX'...")
            # Use .func or .coroutine depending on LangChain version, using .coroutine here for async tools
            res = await get_stock_quote.func("VIX") if hasattr(get_stock_quote, 'func') and get_stock_quote.func else await get_stock_quote.coroutine("VIX")
            
            if isinstance(res, dict) and res.get("source") == "Visual TradingView Snapshot (Fallback)":
                print(f"  OK: Fallback successfully triggered. (Price: {res['price']})")
                results["pass"] += 1
            else:
                print(f"  FAIL: Fallback not detected. Result: {res}")
                results["fail"] += 1

    # 4. Anti-Hang Watchdog Check
    print("\n[4] ANTI-HANG WATCHDOG")
    # We want to ensure get_stock_quote returns before our 20s watchdog if fetching history
    # Note: get_stock_quote for single ticker uses Ticker.fast_info if use_fast_path=True,
    # but the full diagnostic test should check the history fetch path which is often slower.
    with patch("src.tools.finance._fetch_batch_history") as mock_fetch:
        def slow_mock(*args, **kwargs):
            # This should be interrupted by the 15s internal timeout in get_stock_quote OR _fetch_batch_history
            time.sleep(20) 
            return pd.DataFrame()
        mock_fetch.side_effect = slow_mock
        
        print("  Testing 15s internal timeout with 20s blocking history fetch...")
        try:
            start = time.time()
            # Disable fast path to FORCE the slow history path for the watchdog test
            res = await asyncio.wait_for(get_stock_quote.func("AAPL", use_fast_path=False) if hasattr(get_stock_quote, 'func') and get_stock_quote.func else get_stock_quote.coroutine("AAPL", use_fast_path=False), timeout=25.0)
            duration = time.time() - start
            
            if "timed out" in str(res) or "Visual" in str(res):
                print(f"  OK: Tool aborted correctly after {duration:.2f}s (Watchdog held).")
                results["pass"] += 1
            else:
                print(f"  FAIL: Unexpected result: {res}")
                results["fail"] += 1
        except asyncio.TimeoutError:
            print("  FAIL: The tool hung beyond the 20s threshold!")
            results["fail"] += 1

    print(f"\n--- FINAL REPORT: {results['pass']} PASS | {results['fail']} FAIL ---")
    if results["fail"] > 0: sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
