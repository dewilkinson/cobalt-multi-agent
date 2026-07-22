import json
import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os
import glob

PRIMARY_CACHE = "backend/data/brokerage_cache.json"
SECONDARY_CACHE = "data/brokerage_cache.json"
ARCHIVE_PATTERN = "data/archive/BrokerageCacheDailyBackup_*.json"
OUTPUT_PATH = "data/exports/tradezella-import.csv"

eastern = ZoneInfo("America/New_York")
utc = timezone.utc

def get_best_cache_path():
    if os.path.exists(PRIMARY_CACHE):
        return PRIMARY_CACHE
    if os.path.exists(SECONDARY_CACHE):
        return SECONDARY_CACHE
    archive_files = sorted(glob.glob(ARCHIVE_PATTERN))
    if archive_files:
        return archive_files[-1]
    raise FileNotFoundError("No brokerage cache file found")

def extract_trades(target_date_str="2026-07-21"):
    cache_path = get_best_cache_path()
    print(f"Reading trades from: {cache_path}...")
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    trades_to_export = []
    
    for account_name, account_data in data.items():
        if isinstance(account_data, dict) and "activities" in account_data:
            for activity in account_data["activities"]:
                status = str(activity.get("status", "")).capitalize()
                if status and status != "Executed":
                    continue
                
                raw_time = activity.get("trade_date", "") or activity.get("time_placed", "")
                if not raw_time:
                    continue
                
                clean_str = str(raw_time).replace("Z", "")
                if "+" in clean_str:
                    clean_str = clean_str.split("+")[0]
                    
                dt_est = None
                try:
                    if "T" in clean_str:
                        if "." in clean_str:
                            parts = clean_str.split(".")
                            clean_str = parts[0] + "." + parts[1][:6]
                            dt = datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S.%f")
                        else:
                            dt = datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
                        dt_utc = dt.replace(tzinfo=utc)
                        dt_est = dt_utc.astimezone(eastern)
                    else:
                        dt = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S")
                        dt_est = dt.replace(tzinfo=eastern)
                except Exception:
                    pass
                    
                if not dt_est:
                    continue
                    
                trade_date_est = dt_est.strftime("%Y-%m-%d")
                
                # If target_date_str provided, include target date and preceding evening session (after 20:00 EDT)
                if target_date_str:
                    from datetime import datetime as dt_cls, timedelta as td_cls
                    t_dt = dt_cls.strptime(target_date_str, "%Y-%m-%d")
                    prev_date_str = (t_dt - td_cls(days=1)).strftime("%Y-%m-%d")
                    
                    is_valid_date = (trade_date_est == target_date_str) or (trade_date_est == prev_date_str and dt_est.hour >= 20)
                    if not is_valid_date:
                        continue
                    
                tz_date = dt_est.strftime("%m/%d/%Y")
                tz_time = dt_est.strftime("%H:%M:%S")
                
                action = str(activity.get("type", "")).capitalize()
                if not action or action.lower() not in ["buy", "sell"]:
                    action = "Buy" if float(activity.get("units", 0)) > 0 else "Sell"
                
                sym_data = activity.get("symbol", {})
                if isinstance(sym_data, dict):
                    sym = sym_data.get("symbol", "")
                else:
                    sym = str(sym_data)
                
                if not sym:
                    continue
                    
                units = abs(float(activity.get("units", 0) or 0))
                price = float(activity.get("price", 0) or 0)
                
                if units == 0:
                    continue

                is_future = sym.startswith("/") or "future" in account_name.lower() or sym.upper().lstrip("/") in ["MGC", "M2K", "MNK", "MCL", "MYM", "MES", "MNQ", "RTY", "ES", "NQ", "YM", "CL", "GC", "SI", "SIL"]
                clean_sym = sym.lstrip("/").upper()
                spread_type = "Future" if is_future else "Stock"

                # Scale Quantity by CME futures contract multiplier (MGC=10, MCL=100, M2K=5, MYM=0.5, MNK=0.5)
                # so TradeZella's default 1.00 custom CSV parser calculates exact dollar PnL automatically.
                mults = {"MGC": 10.0, "M2K": 5.0, "MYM": 0.5, "MCL": 100.0, "MNK": 0.5, "MES": 5.0, "MNQ": 2.0, "ES": 50.0, "NQ": 20.0, "YM": 5.0, "RTY": 50.0, "GC": 100.0, "CL": 1000.0}
                export_units = units * mults.get(clean_sym, 1.0) if is_future else units

                action_upper = action.upper()

                trades_to_export.append({
                    "Account Name": account_name,
                    "dt": dt_est,
                    "Date / Time": f"{tz_date} {tz_time}",
                    "Date/Time": f"{tz_date} {tz_time}",
                    "Time": f"{tz_date} {tz_time}",
                    "Date": tz_date,
                    "Symbol": clean_sym,
                    "raw_action": action_upper,
                    "Quantity": export_units,
                    "Price": price,
                    "Spread": spread_type,
                    "Commission": float(activity.get("fee", 0) or 0)
                })

    # Sort strictly chronological by datetime and symbol
    trades_to_export.sort(key=lambda x: (x["dt"], x["Symbol"]))
    
    # Calculate position state tracking per symbol to assign exact TradeZella Side (BUY, SELL, SHORT, COVER)
    pos_state = defaultdict(float)
    for t in trades_to_export:
        sym = t["Symbol"]
        q = t["Quantity"]
        is_buy_act = t["raw_action"] in ["BUY", "BTO", "BTC"]
        cur_pos = pos_state[sym]
        
        if is_buy_act:
            t["Side"] = "BUY"
            pos_state[sym] += q
        else: # SELL
            t["Side"] = "SELL"
            pos_state[sym] -= q

    # Filter out unclosed / open trade quantities per symbol so only fully closed trade legs are exported
    symbol_closed_trades = []
    sym_groups = defaultdict(list)
    for t in trades_to_export:
        sym_groups[t["Symbol"]].append(t)
        
    for sym, t_list in sym_groups.items():
        total_buy = sum(t["Quantity"] for t in t_list if t["Side"] == "BUY")
        total_sell = sum(t["Quantity"] for t in t_list if t["Side"] == "SELL")
        matched_qty = min(total_buy, total_sell)
        
        if matched_qty == 0:
            continue
            
        cur_buy = 0.0
        cur_sell = 0.0
        for t in t_list:
            q = t["Quantity"]
            if t["Side"] == "BUY":
                if cur_buy < matched_qty:
                    allowed = min(q, matched_qty - cur_buy)
                    cur_buy += allowed
                    t_copy = dict(t)
                    t_copy["Quantity"] = allowed
                    symbol_closed_trades.append(t_copy)
            else:
                if cur_sell < matched_qty:
                    allowed = min(q, matched_qty - cur_sell)
                    cur_sell += allowed
                    t_copy = dict(t)
                    t_copy["Quantity"] = allowed
                    symbol_closed_trades.append(t_copy)

    trades_to_export = symbol_closed_trades

    # Final sort chronological
    trades_to_export.sort(key=lambda x: (x["dt"], x["Symbol"]))
    
    # Strip temporary helper keys before writing CSV
    for t in trades_to_export:
        t.pop("dt", None)
        t.pop("raw_action", None)
    
    # Write to CSV files (Combined, Futures-only, Stocks-only)
    tz_headers = ["Account Name", "Date / Time", "Date/Time", "Time", "Date", "Symbol", "Side", "Quantity", "Price", "Spread", "Commission"]
    
    futures_trades = [t for t in trades_to_export if t["Spread"] == "Future"]
    stocks_trades = [t for t in trades_to_export if t["Spread"] == "Stock"]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    futures_path = "data/exports/tradezella-import-futures.csv"
    stocks_path = "data/exports/tradezella-import-stocks.csv"

    # Write combined CSV
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=tz_headers)
        writer.writeheader()
        writer.writerows(trades_to_export)

    # Write Futures CSV
    with open(futures_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=tz_headers)
        writer.writeheader()
        writer.writerows(futures_trades)

    # Write Stocks CSV
    with open(stocks_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=tz_headers)
        writer.writeheader()
        writer.writerows(stocks_trades)

    print(f"Success! Exported for Eastern Date {target_date_str}:")
    print(f"  - Combined: {len(trades_to_export)} trades -> {OUTPUT_PATH}")
    print(f"  - Futures:  {len(futures_trades)} trades -> {futures_path}")
    print(f"  - Stocks:   {len(stocks_trades)} trades -> {stocks_path}")
    
    # Sync to Google Drive
    try:
        sys.path.insert(0, os.path.abspath("backend"))
        from src.services.gdrive_backup_service import sync_file_to_gdrive
        sync_file_to_gdrive(OUTPUT_PATH, "exports/tradezella-import.csv")
        sync_file_to_gdrive(futures_path, "exports/tradezella-import-futures.csv")
        sync_file_to_gdrive(stocks_path, "exports/tradezella-import-stocks.csv")
    except Exception as e:
        print(f"Google Drive sync warning: {e}")

    return trades_to_export

if __name__ == "__main__":
    trades = extract_trades("2026-07-21")
