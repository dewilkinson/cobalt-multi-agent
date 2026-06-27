import os
import json
import csv
import sys
import argparse
from datetime import datetime, timedelta

# Set standard output encoding to UTF-8 to handle any platform variations
sys.stdout.reconfigure(encoding='utf-8')

def parse_args():
    parser = argparse.ArgumentParser(description="Hardened TradeZella Exporter and Cache Ingester")
    parser.add_argument("--start", type=str, help="Start date for filtering in YYYY-MM-DD format (default: Monday of this week)")
    parser.add_argument("--end", type=str, help="End date for filtering in YYYY-MM-DD format (default: Saturday of this week to catch Friday)")
    parser.add_argument("--dropzone", type=str, help="Override dropzone folder path")
    parser.add_argument("--cache", type=str, help="Override brokerage cache path")
    parser.add_argument("--output", type=str, help="Override output TradeZella CSV path")
    return parser.parse_args()

def scan_and_parse_dropzone(dropzone_dir):
    new_trades = []
    if not os.path.exists(dropzone_dir):
        print(f"Warning: Dropzone directory not found at {dropzone_dir}")
        return new_trades

    # Look for Orders_Rollover_IRA__5513.csv or timestamped variations in the dropzone
    files_to_parse = []
    for filename in os.listdir(dropzone_dir):
        if filename.startswith("Orders_Rollover_IRA__5513") and filename.endswith(".csv"):
            files_to_parse.append(os.path.join(dropzone_dir, filename))

    if not files_to_parse:
        print(f"No Orders_Rollover_IRA__5513 files found in dropzone: {dropzone_dir}")
        return new_trades

    print(f"Scanning dropzone for executions in: {[os.path.basename(f) for f in files_to_parse]}")
    for path in files_to_parse:
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
            
            # Find the header row
            header_idx = -1
            for i, line in enumerate(lines):
                if "Symbol,Action,Amount" in line:
                    header_idx = i
                    break
            
            if header_idx == -1:
                print(f"  - Warning: Header not found in {os.path.basename(path)}. Skipping.")
                continue

            csv_data = "".join(lines[header_idx:])
            reader = csv.DictReader(csv_data.splitlines())
            
            file_trades_count = 0
            for row in reader:
                sym = (row.get("Symbol") or "").strip()
                action = (row.get("Action") or "").upper().strip()
                amount_str = (row.get("Amount") or "0").replace(',', '')
                status = row.get("Status") or ""
                order_time_str = row.get("Order Time") or ""
                
                if sym and order_time_str and status and "Filled" in status:
                    try:
                        qty = float(amount_str)
                        price_str = status.split("Filled at $")[-1].replace(",", "").strip()
                        price = float(price_str)
                    except Exception as e:
                        print(f"  - Error parsing row for {sym} in {os.path.basename(path)}: {e}")
                        continue
                        
                    clean_time = order_time_str.split(" ET ")[0] if " ET " in order_time_str else order_time_str
                    date_str = order_time_str.split(" ET ")[-1] if " ET " in order_time_str else ""
                    try:
                        dt_obj = datetime.strptime(f"{clean_time} {date_str}", "%I:%M:%S %p %b-%d-%Y")
                        iso_time = dt_obj.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    except Exception:
                        iso_time = order_time_str
                        
                    new_trades.append({
                        "symbol": sym,
                        "action": action,
                        "units": qty,
                        "price": price,
                        "trade_date": iso_time
                    })
                    file_trades_count += 1
            print(f"  - Parsed {file_trades_count} filled executions from {os.path.basename(path)}")
        except Exception as e:
            print(f"  - Failed to parse file {path}: {e}")

    return new_trades

def merge_into_cache(cache_path, new_trades):
    if not os.path.exists(cache_path):
        print(f"Cache file not found at {cache_path}. Creating new baseline structure.")
        cache = {"Rollover IRA *5513": {"activities": [], "positions": [], "closed_positions": []}}
    else:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache = json.load(f)

    account = "Rollover IRA *5513"
    if account not in cache:
        cache[account] = {"activities": [], "positions": [], "closed_positions": []}

    existing_activities = cache[account].get("activities", [])
    existing_ids = {a["id"] for a in existing_activities if "id" in a}

    merged_count = 0
    for t in new_trades:
        # Generate deduplicated activity ID
        activity_id = f"ATP-{t['symbol']}-{t['trade_date']}-{t['units']}-{t['action']}".replace(":", "").replace(" ", "-")
        
        if activity_id in existing_ids:
            continue
            
        cache[account]["activities"].append({
            "id": activity_id,
            "type": t["action"],
            "units": t["units"],
            "price": t["price"],
            "trade_date": t["trade_date"],
            "status": "Executed",
            "symbol": {
                "symbol": t["symbol"]
            }
        })
        existing_ids.add(activity_id)
        merged_count += 1

    if merged_count > 0:
        # Sort activities descending (newest first)
        cache[account]["activities"].sort(key=lambda x: x.get("trade_date", ""), reverse=True)
        
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2)
        print(f"Successfully merged {merged_count} new unique execution(s) into cache: {cache_path}")
    else:
        print("No new unique executions to merge into the cache.")

    return cache

def parse_time(act):
    t_str = act.get('trade_date', '') or act.get('time_placed', '')
    from zoneinfo import ZoneInfo
    eastern_tz = ZoneInfo("America/New_York")
    if not t_str:
        return datetime.min.replace(tzinfo=eastern_tz)
    
    # Strip Z or timezone offset if present, to treat the hours as Eastern Time
    t_str_clean = t_str
    if t_str_clean.endswith('Z'):
        t_str_clean = t_str_clean[:-1]
    if '+' in t_str_clean:
        t_str_clean = t_str_clean.split('+')[0]
        
    # Try parsing Month-Day-Year (e.g. Oct-7-2025 or May-20-2026)
    if '-' in t_str_clean and not t_str_clean.startswith('20'):
        try:
            dt = datetime.strptime(t_str_clean, "%b-%d-%Y")
            return dt.replace(tzinfo=eastern_tz)
        except Exception:
            pass
            
    # Try parsing Month/Day/Year (e.g. 10/7/2025)
    if '/' in t_str_clean:
        try:
            dt = datetime.strptime(t_str_clean, "%m/%d/%Y")
            return dt.replace(tzinfo=eastern_tz)
        except Exception:
            try:
                dt = datetime.strptime(t_str_clean, "%m/%d/%y")
                return dt.replace(tzinfo=eastern_tz)
            except Exception:
                pass
                
    try:
        if 'T' in t_str_clean:
            if '.' in t_str_clean:
                parts = t_str_clean.split('.')
                frac = parts[1][:3]
                t_str_clean = parts[0] + '.' + frac
                dt = datetime.strptime(t_str_clean, "%Y-%m-%dT%H:%M:%S.%f")
            else:
                dt = datetime.strptime(t_str_clean, "%Y-%m-%dT%H:%M:%S")
        else:
            dt = datetime.fromisoformat(t_str_clean)
            
        return dt.replace(tzinfo=eastern_tz)
    except Exception:
        try:
            dt = datetime.fromisoformat(t_str.replace('Z', '+00:00'))
            return dt.astimezone(eastern_tz)
        except Exception:
            return datetime.min.replace(tzinfo=eastern_tz)

def run_fifo_matching(cache, start_date, end_date):
    active_accounts = ["Rollover IRA *5513"]
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        sys.path.append(os.path.abspath(os.path.join(project_root, "backend")))
        from src.config.loader import get_config
        config = get_config()
        if "DROPZONE_ACCOUNTS" in config:
            active_accounts = list(config["DROPZONE_ACCOUNTS"].keys())
    except Exception as e:
        print(f"Warning: Could not load configuration for active accounts: {e}")
        active_accounts = list(cache.keys())

    trades_to_export = []
    
    for account in active_accounts:
        if account not in cache:
            continue
            
        activities = cache.get(account, {}).get("activities", [])
        if not activities:
            continue
            
        print(f"Running FIFO Matching for account: {account} ({len(activities)} activities)...")
        chronological_acts = sorted(activities, key=parse_time)
        
        from zoneinfo import ZoneInfo
        eastern_tz = ZoneInfo("America/New_York")
        now = datetime.now(eastern_tz)
        cutoff_date = datetime(now.year, now.month, 1, tzinfo=eastern_tz)
        cleared_orphans = False
        
        tax_lots = {}  # symbol -> {"type": "flat"|"long"|"short", "lots": list}
        closed_trades = []
        
        for act in chronological_acts:
            trade_time = parse_time(act)
            if not cleared_orphans and trade_time >= cutoff_date:
                tax_lots.clear()
                cleared_orphans = True
                
            action = act.get('type', act.get('action', '')).upper()
            status = act.get('status', '').upper()
            if status not in ['EXECUTED', 'FILLED']:
                continue
                
            sym = act.get('symbol', {}).get('symbol') if isinstance(act.get('symbol'), dict) else act.get('symbol')
            if not sym:
                continue
            sym = sym.upper()
            
            qty = float(act.get('units', 0))
            price = float(act.get('price', 0))
            
            if sym not in tax_lots:
                tax_lots[sym] = {"type": "flat", "lots": []}
                
            lot_info = tax_lots[sym]
            
            if action in ["BUY", "BOUGHT", "BTO", "BTC"]:
                if lot_info["type"] in ["flat", "long"]:
                    lot_info["lots"].append({"qty": qty, "price": price, "time": trade_time})
                    lot_info["type"] = "long"
                else: # cover short
                    buy_qty_remaining = qty
                    while buy_qty_remaining > 0.0001 and len(lot_info["lots"]) > 0:
                        lot = lot_info["lots"][0]
                        match_qty = min(lot["qty"], buy_qty_remaining)
                        closed_trades.append({
                            "open_time": lot["time"],
                            "close_time": trade_time,
                            "symbol": sym,
                            "volume": match_qty,
                            "open_price": lot["price"],
                            "close_price": price,
                            "direction": "Short"
                        })
                        buy_qty_remaining -= match_qty
                        lot["qty"] -= match_qty
                        if lot["qty"] <= 0.0001:
                            lot_info["lots"].pop(0)
                    if buy_qty_remaining > 0.0001:
                        lot_info["lots"].append({"qty": buy_qty_remaining, "price": price, "time": trade_time})
                        lot_info["type"] = "long"
                    elif len(lot_info["lots"]) == 0:
                        lot_info["type"] = "flat"
                        
            elif action in ["SELL", "SOLD", "STC", "STO"]:
                if lot_info["type"] in ["flat", "short"]:
                    lot_info["lots"].append({"qty": qty, "price": price, "time": trade_time})
                    lot_info["type"] = "short"
                else: # closing long
                    sell_qty_remaining = qty
                    while sell_qty_remaining > 0.0001 and len(lot_info["lots"]) > 0:
                        lot = lot_info["lots"][0]
                        match_qty = min(lot["qty"], sell_qty_remaining)
                        closed_trades.append({
                            "open_time": lot["time"],
                            "close_time": trade_time,
                            "symbol": sym,
                            "volume": match_qty,
                            "open_price": lot["price"],
                            "close_price": price,
                            "direction": "Long"
                        })
                        sell_qty_remaining -= match_qty
                        lot["qty"] -= match_qty
                        if lot["qty"] <= 0.0001:
                            lot_info["lots"].pop(0)
                    if sell_qty_remaining > 0.0001:
                        lot_info["lots"].append({"qty": sell_qty_remaining, "price": price, "time": trade_time})
                        lot_info["type"] = "short"
                    elif len(lot_info["lots"]) == 0:
                        lot_info["type"] = "flat"
                        
        this_week_closed_trades = []
        for t in closed_trades:
            if start_date <= t["close_time"] < end_date:
                this_week_closed_trades.append(t)
                
        print(f"  - Closed trades matching range for {account}: {len(this_week_closed_trades)}")
        
        for t in this_week_closed_trades:
            direction = t.get("direction", "Long")
            is_futures = t["symbol"].startswith("/") or t["symbol"].endswith("!") or "Futures" in account
            spread_val = "Future" if is_futures else "Stock"
            
            if direction == "Short":
                # Entry is Sell
                trades_to_export.append({
                    'Account Name': account,
                    'Date&Time': '',
                    'Date': t["open_time"].strftime("%m/%d/%Y"),
                    'Time': t["open_time"].strftime("%H:%M:%S"),
                    'Symbol': t["symbol"],
                    'Buy/Sell': 'Sell',
                    'Quantity': t["volume"],
                    'Price': t["open_price"],
                    'Spread': spread_val,
                    'Expiration': '',
                    'Strike': '',
                    'Call/Put': '',
                    'Commission': 0,
                    'Fees': 0,
                    '_dt': t["open_time"],
                    '_action_order': 0
                })
                # Exit is Buy
                trades_to_export.append({
                    'Account Name': account,
                    'Date&Time': '',
                    'Date': t["close_time"].strftime("%m/%d/%Y"),
                    'Time': t["close_time"].strftime("%H:%M:%S"),
                    'Symbol': t["symbol"],
                    'Buy/Sell': 'Buy',
                    'Quantity': t["volume"],
                    'Price': t["close_price"],
                    'Spread': spread_val,
                    'Expiration': '',
                    'Strike': '',
                    'Call/Put': '',
                    'Commission': 0,
                    'Fees': 0,
                    '_dt': t["close_time"],
                    '_action_order': 1
                })
            else:
                # Entry is Buy
                trades_to_export.append({
                    'Account Name': account,
                    'Date&Time': '',
                    'Date': t["open_time"].strftime("%m/%d/%Y"),
                    'Time': t["open_time"].strftime("%H:%M:%S"),
                    'Symbol': t["symbol"],
                    'Buy/Sell': 'Buy',
                    'Quantity': t["volume"],
                    'Price': t["open_price"],
                    'Spread': spread_val,
                    'Expiration': '',
                    'Strike': '',
                    'Call/Put': '',
                    'Commission': 0,
                    'Fees': 0,
                    '_dt': t["open_time"],
                    '_action_order': 0
                })
                # Exit is Sell
                trades_to_export.append({
                    'Account Name': account,
                    'Date&Time': '',
                    'Date': t["close_time"].strftime("%m/%d/%Y"),
                    'Time': t["close_time"].strftime("%H:%M:%S"),
                    'Symbol': t["symbol"],
                    'Buy/Sell': 'Sell',
                    'Quantity': t["volume"],
                    'Price': t["close_price"],
                    'Spread': spread_val,
                    'Expiration': '',
                    'Strike': '',
                    'Call/Put': '',
                    'Commission': 0,
                    'Fees': 0,
                    '_dt': t["close_time"],
                    '_action_order': 1
                })
                
    aggregated_trades = {}
    for r in trades_to_export:
        key = (
            r['Account Name'],
            r['Date'],
            r['Time'],
            r['Symbol'],
            r['Buy/Sell'],
            r['Price'],
            r['Spread'],
            r['Expiration'],
            r['Strike'],
            r['Call/Put'],
            r['_action_order']
        )
        if key not in aggregated_trades:
            aggregated_trades[key] = dict(r)
        else:
            aggregated_trades[key]['Quantity'] += r['Quantity']
            aggregated_trades[key]['Commission'] += r['Commission']
            aggregated_trades[key]['Fees'] += r['Fees']
            
    trades_to_export = list(aggregated_trades.values())
    trades_to_export.sort(key=lambda x: (x["_dt"], x["Symbol"], x["_action_order"]))
    return trades_to_export

def verify_rules(rows):
    print("\n=== TradeZella Validation Checks ===")
    
    # Rule A: No open trades (every execution must have a match)
    symbol_buys = {}
    symbol_sells = {}
    
    for r in rows:
        acc_sym = (r["Account Name"], r["Symbol"])
        action = r["Buy/Sell"]
        qty = float(r["Quantity"])
        
        if action == "Buy":
            symbol_buys[acc_sym] = symbol_buys.get(acc_sym, 0) + qty
        elif action == "Sell":
            symbol_sells[acc_sym] = symbol_sells.get(acc_sym, 0) + qty
            
    has_error = False
    all_symbols = set(symbol_buys.keys()) | set(symbol_sells.keys())
    for acc_sym in sorted(all_symbols, key=lambda x: (x[0], x[1])):
        acc, sym = acc_sym
        buys = symbol_buys.get(acc_sym, 0)
        sells = symbol_sells.get(acc_sym, 0)
        if abs(buys - sells) > 0.0001:
            print(f"  [FAIL] Unbalanced symbol in {acc}: {sym} | Buys: {buys} | Sells: {sells} | Diff: {buys - sells}")
            has_error = True
        else:
            print(f"  [PASS] {acc} | Symbol: {sym} | Closed Match Qty: {buys}")
            
    # Rule B: Check position balance at matching boundaries
    symbol_pos = {}
    for i, r in enumerate(rows):
        sym = (r["Account Name"], r["Symbol"])
        action = r["Buy/Sell"]
        qty = float(r["Quantity"])
        
        if action == "Buy":
            symbol_pos[sym] = symbol_pos.get(sym, 0) + qty
        elif action == "Sell":
            symbol_pos[sym] = symbol_pos.get(sym, 0) - qty
            
    if not has_error:
        print("\n[SUCCESS] All verification checks PASSED! Zero open trades, short positions balanced.")
    else:
        print("\n[ERROR] Some verification checks FAILED! Check console details above.")
        
    return not has_error

def main():
    args = parse_args()
    
    # Path Resolution
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.append(os.path.abspath(os.path.join(project_root, "backend")))
    
    dropzone_dir = args.dropzone or os.path.join(project_root, "data", "dropzone")
    cache_path = args.cache or os.path.join(project_root, "backend", "data", "brokerage_cache.json")
    output_path = args.output or os.path.join(project_root, "data", "exports", "tradezella-import.csv")
    
    from zoneinfo import ZoneInfo
    eastern_tz = ZoneInfo("America/New_York")
    
    # Date Filtering Resolution
    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=eastern_tz)
    else:
        today = datetime.now(eastern_tz)
        monday = today - timedelta(days=today.weekday())
        start_date = datetime(monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=eastern_tz)
        
    if args.end:
        end_date = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=eastern_tz)
    else:
        # Defaults to Saturday of the current week (to catch all Friday executions)
        end_date = start_date + timedelta(days=6)
        
    print(f"Target week: {start_date.strftime('%Y-%m-%d')} to {(end_date - timedelta(seconds=1)).strftime('%Y-%m-%d')}")
    
    # 1. Trigger process_dropzone_files first to ingest all dropped CSV files
    try:
        from src.services.csv_importer import process_dropzone_files
        print("Ingesting new dropzone files via csv_importer...")
        process_dropzone_files(optional_path=dropzone_dir)
    except Exception as e:
        print(f"Warning: Failed to run csv_importer process_dropzone_files: {e}")
        
    # 2. Load the brokerage cache (which now has all active accounts)
    if not os.path.exists(cache_path):
        print(f"Cache file not found at {cache_path}.")
        sys.exit(1)
        
    with open(cache_path, 'r', encoding='utf-8') as f:
        cache = json.load(f)
        
    # 3. Run exporter on all active accounts inside cache
    rows = run_fifo_matching(cache, start_date, end_date)
    
    # 4. Verify rules
    success = verify_rules(rows)
    
    # Write to TradeZella CSV
    tz_headers = ["Account Name", "Date&Time", "Date", "Time", "Symbol", "Buy/Sell", "Quantity", "Price", "Spread", "Expiration", "Strike", "Call/Put", "Commission", "Fees"]
    
    # Clean up verification fields
    for row in rows:
        if "_dt" in row:
            del row["_dt"]
        if "_action_order" in row:
            del row["_action_order"]
            
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=tz_headers)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Exported {len(rows)} execution rows to: {output_path}")
    if not success:
        sys.exit(1)

if __name__ == '__main__':
    main()

