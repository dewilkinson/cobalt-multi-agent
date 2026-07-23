import os
import sys
import time
import json
from datetime import datetime
from zoneinfo import ZoneInfo

# Resolve project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(project_root)
sys.path.insert(0, "backend")

from src.server.routes.scanner import run_weekly_5m_replay_backtest, TRENDS_CACHE, save_trends_cache
from src.tools.finance import _fetch_batch_history, _extract_ticker_data

import sqlite3

FUTURES_SYMBOLS = [
    "/ES", "/NQ", "/YM", "/RTY", "/CL", "/GC", "/SI", "/NG", "/ZB", "/ZN", "/ZF", "/ZT",
    "/MES", "/MNQ", "/MYM", "/M2K", "/MCL", "/MGC", "/MNK", "/NKD",
    "ES=F", "NQ=F", "YM=F", "RTY=F", "CL=F", "GC=F", "SI=F", "NG=F"
]
MACRO_SYMBOLS = ["SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "USO", "TLT", "VIX", "BTC-USD"] + FUTURES_SYMBOLS

def get_watchlist_symbols():
    """Extract all active imported watchlist tickers from watchlists.db + standard macro symbols."""
    symbols = set(MACRO_SYMBOLS)
    
    # 1. Query SQLite watchlists.db directly
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "watchlists.db"))
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT symbol FROM watchlists")
            rows = cursor.fetchall()
            for r in rows:
                if r[0] and isinstance(r[0], str):
                    symbols.add(r[0].strip().upper())
            conn.close()
            print(f"Successfully loaded {len(rows)} distinct symbols from {db_path}")
        except Exception as e:
            print(f"Warning: Failed to query {db_path}: {e}")
            
    # 2. Add any additional symbols in trends_cache.json if present
    if os.path.exists("backend/data/trends_cache.json"):
        try:
            with open("backend/data/trends_cache.json", "r", encoding="utf-8") as f:
                cache = json.load(f)
                symbols.update(cache.keys())
        except Exception as e:
            print(f"Warning: Failed to load trends_cache.json: {e}")

    # Clean up empty strings or invalid symbols
    valid_symbols = sorted([s.strip().upper() for s in symbols if s and isinstance(s, str)])
    return valid_symbols

def main():
    eastern = ZoneInfo("America/New_York")
    now_et = datetime.now(eastern)
    
    print("=" * 60)
    print(" Daily Backtest Job Execution")
    print(f" Timestamp (ET): {now_et.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    symbols = get_watchlist_symbols()
    print(f"Target Symbol Database: {len(symbols)} tickers")
    print(f"Macro Tickers Included: {', '.join(MACRO_SYMBOLS)}")
    print("-" * 60)

    batch_size = 15
    updated_count = 0
    total_trades = 0
    total_rejections = 0

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        print(f"\n[Batch {i//batch_size + 1}/{(len(symbols) + batch_size - 1)//batch_size}] Processing: {', '.join(batch)}")
        
        try:
            raw5 = _fetch_batch_history(batch, "30d", "5m")
            raw1h = _fetch_batch_history(batch, "3mo", "1h")
            raw1d = _fetch_batch_history(batch, "2y", "1d")
        except Exception as batch_err:
            print(f"Batch fetch error: {batch_err}")
            continue

        for sym in batch:
            try:
                df5 = _extract_ticker_data(raw5, sym)
                df1h = _extract_ticker_data(raw1h, sym)
                df1d = _extract_ticker_data(raw1d, sym)
                
                if df5 is None or df5.empty:
                    print(f"  [{sym:<6}] No 5m market data returned, skipping.")
                    continue
                    
                clean_sym = sym.lstrip("/^").upper()
                is_future = sym in FUTURES_SYMBOLS or sym.endswith("=F") or sym.startswith("/") or clean_sym in ["ES", "MES", "NQ", "MNQ", "YM", "MYM", "RTY", "M2K", "CL", "MCL", "GC", "MGC", "NKD", "MNK"]
                stats = run_weekly_5m_replay_backtest(df5, df1h, df1d, sym, is_future=is_future, target_window="session")
                
                if sym not in TRENDS_CACHE:
                    TRENDS_CACHE[sym] = {}
                    
                TRENDS_CACHE[sym]["crt_15m_stats"] = {"success": stats["success"], "fail": stats["fail"]}
                TRENDS_CACHE[sym]["crt_1h_stats"] = {"success": stats["success"], "fail": stats["fail"]}
                TRENDS_CACHE[sym]["crt_4h_stats"] = {"success": stats["success"], "fail": stats["fail"]}
                TRENDS_CACHE[sym]["trade_ledger"] = stats["ledger"]
                TRENDS_CACHE[sym]["rejected_trades"] = stats.get("rejected_trades", [])
                TRENDS_CACHE[sym]["backtest_pending"] = False
                TRENDS_CACHE[sym]["timestamp"] = time.time()
                
                updated_count += 1
                total_trades += len(stats["ledger"])
                total_rejections += len(stats.get("rejected_trades", []))
                
                print(f"  [{sym:<6}] Completed: {stats['success']} Wins / {stats['fail']} Losses | Trades: {len(stats['ledger'])} | Rejections: {len(stats.get('rejected_trades', []))}")
            except Exception as s_err:
                print(f"  [{sym:<6}] Backtest error: {s_err}")
                
        save_trends_cache()
        time.sleep(0.5)

    print("\n" + "=" * 60)
    print(f" Daily Backtest Job Finished Successfully")
    print(f" Tickers Processed: {updated_count}/{len(symbols)}")
    print(f" Total Trades Executed: {total_trades}")
    print(f" Total Filtered Rejections: {total_rejections}")
    print("=" * 60)

if __name__ == "__main__":
    main()
