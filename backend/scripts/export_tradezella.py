import json
import csv
from collections import defaultdict, deque
from datetime import datetime, timedelta
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, BASE_DIR)

MULTIPLIERS = {
    'MNQ': 2.0,
    'MES': 5.0,
    'MGC': 10.0,
    'MCL': 10.0,
    'MYM': 0.5,
    'M2K': 5.0,
    'NQ': 20.0,
    'ES': 50.0,
    'GC': 100.0,
    'CL': 1000.0,
    'YM': 5.0,
    'RTY': 50.0
}

def get_cache():
    try:
        from src.services.brokerage_cache import BrokerageCache
        cache = BrokerageCache._load_cache()
        if cache:
            return cache
    except Exception:
        pass
        
    cache_paths = [
        os.path.join(ROOT_DIR, "data", "brokerage_cache.json"),
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

def pair_closed_trades(activities):
    parsed = []
    for act in activities:
        st = str(act.get('status', '')).upper()
        if st and any(s in st for s in ['CANCEL', 'REJECT', 'DECLINE', 'UNFILLED']):
            continue
        dt = parse_datetime(act.get('trade_date') or act.get('time_placed'))
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
        action = 'BUY' if 'BUY' in str(act.get('type', '')).upper() or act.get('action') == 'BUY' else 'SELL'
        qty = float(act.get('units') or act.get('quantity') or 0)
        price = float(act.get('price') or 0)
        comm = float(act.get('commission') or 0)
        fees = float(act.get('fee') or act.get('fees') or 0)
        parsed.append({
            'dt': dt, 'sym': sym, 'raw_sym': raw_sym, 
            'action': action, 'qty': qty, 'price': price, 
            'comm': comm, 'fees': fees
        })
    
    parsed.sort(key=lambda x: x['dt'])
    
    open_positions = defaultdict(deque)
    closed_trades = []
    trade_counter = 2952000000

    for item in parsed:
        sym = item['sym']
        q = open_positions[sym]
        
        if q and q[0]['action'] != item['action']:
            fill_qty = item['qty']
            item_side = item['action']
            trade_type = 'Long' if q[0]['action'] == 'BUY' else 'Short'
            
            while fill_qty > 1e-5 and q and q[0]['action'] != item_side:
                open_fill = q[0]
                matched_qty = min(fill_qty, open_fill['qty'])
                
                entry_dt = open_fill['dt']
                exit_dt = item['dt']
                entry_p = open_fill['price']
                exit_p = item['price']
                
                mult = MULTIPLIERS.get(sym, 1.0)
                if trade_type == 'Long':
                    pnl = (exit_p - entry_p) * matched_qty * mult
                else:
                    pnl = (entry_p - exit_p) * matched_qty * mult
                
                dur_secs = max(0, int((exit_dt - entry_dt).total_seconds()))
                dur_str = f"{dur_secs//60:02d}:{dur_secs%60:02d}.0"
                
                contract_name = sym + "U6" if len(sym) <= 3 and not sym.endswith("6") else sym

                entry_fee_part = (open_fill['fees'] * (matched_qty / open_fill['raw_qty'])) if open_fill['raw_qty'] > 0 else 0
                exit_fee_part = (item['fees'] * (matched_qty / item['qty'])) if item['qty'] > 0 else 0
                
                entry_comm_part = (open_fill['comm'] * (matched_qty / open_fill['raw_qty'])) if open_fill['raw_qty'] > 0 else 0
                exit_comm_part = (item['comm'] * (matched_qty / item['qty'])) if item['qty'] > 0 else 0

                trade_counter += 1
                closed_trades.append({
                    'Id': str(trade_counter),
                    'ContractName': contract_name,
                    'EnteredAt': entry_dt.strftime('%m/%d/%Y %H:%M:%S -04:00'),
                    'ExitedAt': exit_dt.strftime('%m/%d/%Y %H:%M:%S -04:00'),
                    'EntryPrice': round(entry_p, 4),
                    'ExitPrice': round(exit_p, 4),
                    'Fees': round(entry_fee_part + exit_fee_part, 2),
                    'PnL': round(pnl, 2),
                    'Size': int(matched_qty) if matched_qty.is_integer() else matched_qty,
                    'Type': trade_type,
                    'TradeDay': entry_dt.strftime('%m/%d/%Y 00:00:00 -05:00'),
                    'TradeDuration': dur_str,
                    'Commissions': round(entry_comm_part + exit_comm_part, 2),
                    '_raw_date': entry_dt.strftime('%Y-%m-%d'),
                    '_exit_raw_date': exit_dt.strftime('%Y-%m-%d')
                })
                
                fill_qty -= matched_qty
                open_fill['qty'] -= matched_qty
                if open_fill['qty'] <= 1e-5:
                    q.popleft()
            
            if fill_qty > 1e-5:
                q.append({'dt': item['dt'], 'action': item['action'], 'qty': fill_qty, 'raw_qty': item['qty'], 'price': item['price'], 'comm': item['comm'], 'fees': item['fees']})
        else:
            q.append({'dt': item['dt'], 'action': item['action'], 'qty': item['qty'], 'raw_qty': item['qty'], 'price': item['price'], 'comm': item['comm'], 'fees': item['fees']})

    return closed_trades

def export_tradezella(start_date=None, end_date=None, target_account=None):
    cache = get_cache()
    if not cache:
        print("[ERROR]: BrokerageCache is empty or could not be loaded.")
        return

    # Single Export Directory: Workspace Root data/exports
    exports_dir = os.path.join(ROOT_DIR, "data", "exports")
    os.makedirs(exports_dir, exist_ok=True)

    native_headers = [
        "Id", "ContractName", "EnteredAt", "ExitedAt", "EntryPrice", 
        "ExitPrice", "Fees", "PnL", "Size", "Type", 
        "TradeDay", "TradeDuration", "Commissions"
    ]

    tz_canonical_headers = [
        "Account Name", "Date / Time", "Symbol", "Side", 
        "Quantity", "Price", "Spread", "Expiration", 
        "Strike", "Call/Put", "Commission", "Fees"
    ]

    all_native_trades = []
    account_native_trades = defaultdict(list)

    all_generic_rows = []
    account_generic_rows = defaultdict(list)

    today_str = datetime.now().strftime("%Y-%m-%d")

    for account_name, account_data in cache.items():
        if "TEST" in account_name.upper() or "DUMMY" in account_name.upper():
            continue
        if target_account and target_account.lower() not in account_name.lower():
            continue

        activities = account_data.get("activities", []) if isinstance(account_data, dict) else (account_data if isinstance(account_data, list) else [])
        if not activities:
            continue

        # A. Native Topstep/Tradovate Paired Trades
        closed_trades = pair_closed_trades(activities)
        for t in closed_trades:
            raw_date = t.get("_raw_date")
            if start_date and raw_date < start_date:
                continue
            if end_date and raw_date > end_date:
                continue
            
            clean_t = {k: v for k, v in t.items() if not k.startswith("_")}
            clean_t["_raw_date"] = t.get("_raw_date")
            clean_t["_exit_raw_date"] = t.get("_exit_raw_date")

            all_native_trades.append(clean_t)
            account_native_trades[account_name].append(clean_t)

        # B. Generic Executions Rows
        all_activities = []
        for act in activities:
            st = str(act.get("status", "")).upper()
            if st and any(s in st for s in ["CANCEL", "REJECT", "DECLINE", "UNFILLED"]):
                continue
            dt = parse_datetime(act.get("trade_date") or act.get("time_placed"))
            if not dt:
                continue
            all_activities.append(act)

        all_activities.sort(key=lambda a: parse_datetime(a.get("trade_date") or a.get("time_placed")) or datetime.min)

        for act in all_activities:
            dt = parse_datetime(act.get("trade_date") or act.get("time_placed"))
            date_str = dt.strftime("%Y-%m-%d")

            if start_date and date_str < start_date:
                continue
            if end_date and date_str > end_date:
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

            tz_date = dt.strftime("%m/%d/%Y")
            tz_time = dt.strftime("%H:%M:%S")
            tz_datetime = f"{tz_date} {tz_time}"

            is_futures = raw_sym.startswith("/") or sym in ["MGC", "MNQ", "MES", "MCL", "MYM", "M2K", "NQ", "ES", "GC", "CL", "YM", "RTY"]
            spread_val = "Future" if is_futures else "Stock"

            gen_row = {
                "Account Name": account_name,
                "Date / Time": tz_datetime,
                "Symbol": sym,
                "Side": action,
                "Quantity": int(qty) if qty.is_integer() else qty,
                "Price": round(price, 4),
                "Spread": spread_val,
                "Expiration": "",
                "Strike": "",
                "Call/Put": "",
                "Commission": float(act.get("commission") or 0),
                "Fees": float(act.get("fee") or act.get("fees") or 0),
                "_raw_date": date_str
            }
            all_generic_rows.append(gen_row)
            account_generic_rows[account_name].append(gen_row)

    def write_csv(filename, fieldnames, rows):
        out_path = os.path.join(exports_dir, filename)
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # 1. Output Account Primary Native CSV Files
    for acct_name, trades in account_native_trades.items():
        clean_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in trades]
        fn = sanitize_account_filename(acct_name)
        write_csv(fn, native_headers, clean_rows)

        fn_nat = sanitize_account_filename(acct_name, "native")
        write_csv(fn_nat, native_headers, clean_rows)

    # 2. Output Account Generic Execution CSV Files
    for acct_name, rows in account_generic_rows.items():
        clean_gen = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
        fn_gen = sanitize_account_filename(acct_name, "generic")
        write_csv(fn_gen, tz_canonical_headers, clean_gen)

    # 3. Master Native File (tradezella-import-all.csv)
    master_clean_native = [{k: v for k, v in r.items() if not k.startswith("_")} for r in all_native_trades]
    write_csv("tradezella-import-all.csv", native_headers, master_clean_native)

    # 4. Master Generic File (tradezella-import-all-generic.csv)
    master_clean_gen = [{k: v for k, v in r.items() if not k.startswith("_")} for r in all_generic_rows]
    write_csv("tradezella-import-all-generic.csv", tz_canonical_headers, master_clean_gen)

    # 5. Today's Files (tradezella-import-today.csv & tradezella-import-today-generic.csv)
    today_native_trades = [
        {k: v for k, v in r.items() if not k.startswith("_")}
        for r in all_native_trades 
        if r.get("_raw_date") == today_str or r.get("_exit_raw_date") == today_str
    ]
    write_csv("tradezella-import-today.csv", native_headers, today_native_trades)

    today_generic_rows = [
        {k: v for k, v in r.items() if not k.startswith("_")}
        for r in all_generic_rows 
        if r.get("_raw_date") == today_str
    ]
    write_csv("tradezella-import-today-generic.csv", tz_canonical_headers, today_generic_rows)

    print(f"[EXPORT]: Generated clean exports in root directory: {exports_dir}")

if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else None
    end = sys.argv[2] if len(sys.argv) > 2 else None
    export_tradezella(start, end)
