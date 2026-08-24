import json
import csv
from collections import defaultdict
from datetime import datetime, timedelta
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

def get_cache():
    try:
        from src.services.brokerage_cache import BrokerageCache
        cache = BrokerageCache._load_cache()
        if cache:
            return cache
    except Exception:
        pass
        
    cache_paths = [
        os.path.join(BASE_DIR, "data", "brokerage_cache.json"),
        os.path.join(BASE_DIR, "data", "archive", "BrokerageCacheDailyBackup.json"),
    ]
    for cp in cache_paths:
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

def parse_datetime(dt_str):
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None

def clean_symbol(sym):
    if not sym:
        return ""
    sym = str(sym).strip()
    if sym.startswith("/"):
        sym = sym[1:]
    return sym

def sanitize_account_filename(account_name, suffix=""):
    clean = account_name.replace(" ", "-").replace("*", "").replace("/", "-")
    if suffix:
        return f"tradezella-import-{clean}-{suffix}.csv"
    return f"tradezella-import-{clean}.csv"

def export_tradezella(start_date=None, end_date=None, target_account=None):
    cache = get_cache()
    if not cache:
        print("[ERROR]: BrokerageCache is empty or could not be loaded.")
        return

    exports_dir = os.path.join(BASE_DIR, "data", "exports")
    os.makedirs(exports_dir, exist_ok=True)

    # Standard TradeZella Generic Format Headers (Canonical working TZ format)
    # Header: Account Name,Date / Time,Symbol,Side,Quantity,Price,Spread,Expiration,Strike,Call/Put,Commission,Fees
    tz_canonical_headers = [
        "Account Name", "Date / Time", "Symbol", "Side", 
        "Quantity", "Price", "Spread", "Expiration", 
        "Strike", "Call/Put", "Commission", "Fees"
    ]

    # Alternative TradeZella 14-Column Header format
    tz_split_headers = [
        "Account Name", "Date&Time", "Date", "Time", "Symbol", 
        "Buy/Sell", "Quantity", "Price", "Spread", "Expiration", 
        "Strike", "Call/Put", "Commission", "Fees"
    ]

    all_exported_rows_canonical = []
    account_rows_canonical = defaultdict(list)
    
    all_exported_rows_split = []
    account_rows_split = defaultdict(list)

    today_str = datetime.now().strftime("%Y-%m-%d")

    for account_name, account_data in cache.items():
        if "TEST" in account_name.upper() or "DUMMY" in account_name.upper():
            continue
        if target_account and target_account.lower() not in account_name.lower():
            continue

        activities = account_data.get("activities", []) if isinstance(account_data, dict) else (account_data if isinstance(account_data, list) else [])
        
        all_activities = []
        for act in activities:
            status = str(act.get("status", "")).upper()
            if status and any(s in status for s in ["CANCEL", "REJECT", "DECLINE", "UNFILLED"]):
                continue
            t_date = str(act.get("trade_date", "") or act.get("time_placed", ""))
            if not t_date:
                continue
            all_activities.append(act)

        # Chronological sort
        def act_key(a):
            dt = parse_datetime(a.get("trade_date") or a.get("time_placed"))
            return dt if dt else datetime.min

        all_activities.sort(key=act_key)

        # Deduplicate identical sub-second executions
        deduped = []
        for act in all_activities:
            dt = parse_datetime(act.get("trade_date") or act.get("time_placed"))
            if not dt:
                continue

            raw_sym = ""
            if "universal_symbol" in act and act["universal_symbol"]:
                raw_sym = act["universal_symbol"].get("symbol", "")
            elif "symbol" in act and isinstance(act["symbol"], dict):
                raw_sym = act["symbol"].get("symbol", "")
            elif "symbol" in act and isinstance(act["symbol"], str):
                raw_sym = act["symbol"]

            if not raw_sym:
                continue

            sym = clean_symbol(raw_sym)
            action = "Buy" if "BUY" in str(act.get("type", "")).upper() or act.get("action") == "BUY" else "Sell"
            qty = float(act.get("units") or act.get("quantity") or 0)
            price = float(act.get("price") or 0)

            is_dup = False
            for prev in reversed(deduped[-5:]):
                prev_dt = parse_datetime(prev.get("trade_date") or prev.get("time_placed"))
                prev_sym = prev.get("sym")
                prev_action = prev.get("action")
                if prev_sym == sym and prev_action == action and abs(prev.get("qty", 0) - qty) < 1e-4 and abs(prev.get("price", 0) - price) < 1e-4:
                    if prev_dt and abs((dt - prev_dt).total_seconds()) <= 5:
                        is_dup = True
                        break
            if not is_dup:
                deduped.append({
                    "dt": dt,
                    "sym": sym,
                    "raw_sym": raw_sym,
                    "action": action,
                    "qty": qty,
                    "price": price,
                    "account": account_name,
                    "commission": float(act.get("commission") or 0),
                    "fees": float(act.get("fee") or act.get("fees") or 0)
                })

        for row in deduped:
            dt = row["dt"]
            date_str = dt.strftime("%Y-%m-%d")

            # Date Range Filter
            if start_date and date_str < start_date:
                continue
            if end_date and date_str > end_date:
                continue

            tz_date = dt.strftime("%m/%d/%Y")
            tz_time = dt.strftime("%H:%M:%S")
            tz_datetime = f"{tz_date} {tz_time}"

            # TradeZella generic parser expects "Future" (singular) or "Stock"
            is_futures = row["raw_sym"].startswith("/") or row["sym"] in ["MGC", "MNQ", "MES", "MCL", "MYM", "M2K", "NQ", "ES", "CL", "GC", "YM", "RTY"]
            spread_canonical = "Future" if is_futures else "Stock"
            spread_split = "Futures" if is_futures else "Stock"

            # 1. Canonical Row Format
            canonical_row = {
                "Account Name": account_name,
                "Date / Time": tz_datetime,
                "Symbol": row["sym"],
                "Side": row["action"],
                "Quantity": int(row["qty"]) if row["qty"].is_integer() else row["qty"],
                "Price": round(row["price"], 4),
                "Spread": spread_canonical,
                "Expiration": "",
                "Strike": "",
                "Call/Put": "",
                "Commission": row["commission"],
                "Fees": row["fees"],
                "_raw_date": date_str
            }

            # 2. Split Date/Time Row Format
            split_row = {
                "Account Name": account_name,
                "Date&Time": tz_datetime,
                "Date": tz_date,
                "Time": tz_time,
                "Symbol": row["sym"],
                "Buy/Sell": row["action"],
                "Quantity": int(row["qty"]) if row["qty"].is_integer() else row["qty"],
                "Price": round(row["price"], 4),
                "Spread": spread_split,
                "Expiration": "",
                "Strike": "",
                "Call/Put": "",
                "Commission": row["commission"],
                "Fees": row["fees"],
                "_raw_date": date_str
            }

            all_exported_rows_canonical.append(canonical_row)
            account_rows_canonical[account_name].append(canonical_row)

            all_exported_rows_split.append(split_row)
            account_rows_split[account_name].append(split_row)

    if not all_exported_rows_canonical:
        print("[WARNING]: No executed trades matched the export criteria.")
        return

    # Write Files using utf-8-sig (UTF-8 with BOM for TradeZella CSV compatibility)
    for acct_name, rows in account_rows_canonical.items():
        # Primary working format: tradezella-import-AccountName.csv
        fn = sanitize_account_filename(acct_name)
        out_path = os.path.join(exports_dir, fn)
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=tz_canonical_headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        print(f"Exported Canonical TZ ({len(rows)} trades) -> {fn}")

        # Backup split format: tradezella-import-AccountName-split.csv
        fn_split = sanitize_account_filename(acct_name, "split")
        out_path_split = os.path.join(exports_dir, fn_split)
        with open(out_path_split, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=tz_split_headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(account_rows_split[acct_name])

    # Write Master File (tradezella-import-all.csv)
    master_path = os.path.join(exports_dir, "tradezella-import-all.csv")
    with open(master_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=tz_canonical_headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_exported_rows_canonical)
    print(f"Exported MASTER file ({len(all_exported_rows_canonical)} total trades) -> tradezella-import-all.csv")

    # Write Today's File (tradezella-import-today.csv)
    today_rows = [r for r in all_exported_rows_canonical if r.get("_raw_date") == today_str or r.get("_raw_date") == "2026-08-21"]
    today_path = os.path.join(exports_dir, "tradezella-import-today.csv")
    with open(today_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=tz_canonical_headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(today_rows)
    print(f"Exported TODAY file ({len(today_rows)} session trades) -> tradezella-import-today.csv")

if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else None
    end = sys.argv[2] if len(sys.argv) > 2 else None
    export_tradezella(start, end)
