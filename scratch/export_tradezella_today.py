import json
import csv
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
                
                # If target_date_str provided, filter for that Eastern date
                if target_date_str and trade_date_est != target_date_str:
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

                trades_to_export.append({
                    "Account Name": account_name,
                    "Date&Time": f"{tz_date} {tz_time}",
                    "Date": tz_date,
                    "Time": tz_time,
                    "Symbol": clean_sym,
                    "Buy/Sell": action,
                    "Quantity": units,
                    "Price": price,
                    "Spread": spread_type,
                    "Expiration": "",
                    "Strike": "",
                    "Call/Put": "",
                    "Commission": float(activity.get("fee", 0) or 0),
                    "Fees": 0
                })

    # Sort chronological: Date -> Time -> Symbol -> Action (Buy before Sell)
    trades_to_export.sort(key=lambda x: (x["Date"], x["Time"], x["Symbol"], 0 if x["Buy/Sell"].lower() == "buy" else 1))
    
    # Write to CSV
    tz_headers = ["Account Name", "Date&Time", "Date", "Time", "Symbol", "Buy/Sell", "Quantity", "Price", "Spread", "Expiration", "Strike", "Call/Put", "Commission", "Fees"]
    
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=tz_headers)
        writer.writeheader()
        writer.writerows(trades_to_export)
        
    print(f"Success! {len(trades_to_export)} trades exported to {OUTPUT_PATH} for Eastern Date {target_date_str}")
    
    # Sync to Google Drive
    try:
        from backend.src.services.gdrive_backup_service import sync_file_to_gdrive
        sync_file_to_gdrive(OUTPUT_PATH, "exports/tradezella-import.csv")
    except Exception:
        pass

    return trades_to_export

if __name__ == "__main__":
    trades = extract_trades("2026-07-21")
