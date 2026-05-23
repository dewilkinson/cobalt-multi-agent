import json
import csv
from datetime import datetime, timedelta
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
backup_path = os.path.join(workspace_dir, "data", "archive", "BrokerageCacheDailyBackup.json")
cache_path = os.path.join(workspace_dir, "data", "brokerage_cache.json")
backend_cache_path = os.path.join(workspace_dir, "backend", "data", "brokerage_cache.json")
may18_csv = os.path.join(workspace_dir, "data", "exports", "tradezella-import-20260518-20260518.csv")
dropzone_activity_csv = os.path.join(workspace_dir, "data", "dropzone", "archive", "Activity_All_Accounts.csv")
dropzone_orders_csv = os.path.join(workspace_dir, "data", "dropzone", "archive", "Orders_Rollover_IRA__5513.csv")
output_csv = os.path.join(workspace_dir, "data", "exports", "tradezella-import-this-week.csv")
backend_output_csv = os.path.join(workspace_dir, "backend", "data", "exports", "tradezella-import-this-week.csv")

def load_backup_cache():
    # Start from the clean baseline backup up to May 15
    clean_backup_path = os.path.join(workspace_dir, "data", "archive", "BrokerageCacheDailyBackup_0.json")
    with open(clean_backup_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def parse_may18_trades():
    trades = []
    if not os.path.exists(may18_csv):
        print(f"Warning: May 18 CSV not found at {may18_csv}")
        return trades
        
    with open(may18_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt_str = f"2026-05-18T{row['Time']}.000Z"
            trades.append({
                "account": row["Account Name"],
                "symbol": row["Symbol"],
                "action": row["Buy/Sell"].upper(),
                "units": float(row["Quantity"]),
                "price": float(row["Price"]),
                "trade_date": dt_str
            })
    return trades

def parse_may19_may20_trades():
    trades = []
    if not os.path.exists(dropzone_activity_csv):
        print(f"Warning: Dropzone activity CSV not found at {dropzone_activity_csv}")
        return trades
        
    with open(dropzone_activity_csv, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("Description,Symbol,Quantity"):
            header_idx = i
            break
            
    if header_idx == -1:
        return trades
        
    csv_data = "".join(lines[header_idx:])
    reader = csv.DictReader(csv_data.splitlines())
    
    trades_by_date = {}
    
    for row in reader:
        desc = (row.get("Description") or "").upper()
        sym = (row.get("Symbol") or "").strip()
        account = (row.get("Account") or "").strip()
        qty_str = (row.get("Quantity") or "0").replace(',', '')
        price_str = (row.get("Price") or "0").replace(',', '').replace('$', '')
        settlement_date_str = (row.get("Settlement Date") or "").strip()
        
        action = ""
        if "BOUGHT" in desc:
            action = "BUY"
        elif "SOLD" in desc:
            action = "SELL"
            
        if not action or not sym or settlement_date_str in ["", "--", None]:
            continue
            
        try:
            qty = abs(float(qty_str))
            price = float(price_str)
        except:
            continue
            
        # Parse Settlement Date (format e.g. "May-20-2026")
        # And map to the actual Trade Date (T-1)
        try:
            dt_obj = datetime.strptime(settlement_date_str, "%b-%d-%Y")
            # Map Wednesday May 20 settlement -> Tuesday May 19 trade date
            # Map Thursday May 21 settlement -> Wednesday May 20 trade date
            trade_dt = dt_obj - timedelta(days=1)
            trade_date = trade_dt.strftime("%Y-%m-%d")
        except Exception as e:
            print(f"Error parsing settlement date {settlement_date_str}: {e}")
            continue
            
        if trade_date not in trades_by_date:
            trades_by_date[trade_date] = []
            
        trades_by_date[trade_date].append({
            "account": account,
            "symbol": sym,
            "action": action,
            "units": qty,
            "price": price,
            "date": trade_date
        })
        
    # Assign sequential times for each date to avoid negative balances or short trades
    for date, day_trades in trades_by_date.items():
        # Sort by symbol, and then BUY before SELL so Buys are entered before Sells
        day_trades.sort(key=lambda x: (x["symbol"], 0 if x["action"] == "BUY" else 1))
        
        base_time = datetime.strptime(f"{date}T09:30:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ")
        for idx, t in enumerate(day_trades):
            t_obj = base_time + timedelta(seconds=idx * 300)
            time_str = t_obj.strftime("%H:%M:%S")
            trades.append({
                "account": t["account"],
                "symbol": t["symbol"],
                "action": t["action"],
                "units": t["units"],
                "price": t["price"],
                "trade_date": f"{date}T{time_str}.000Z"
            })
            
    return trades

def parse_may21_trades():
    trades = []
    if not os.path.exists(dropzone_orders_csv):
        print(f"Warning: Dropzone orders CSV not found at {dropzone_orders_csv}")
        return trades
        
    with open(dropzone_orders_csv, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("Symbol,Action,Amount"):
            header_idx = i
            break
            
    if header_idx == -1:
        return trades
        
    csv_data = "".join(lines[header_idx:])
    reader = csv.DictReader(csv_data.splitlines())
    
    # Process filled orders for May 21
    for row in reader:
        sym = (row.get("Symbol") or "").strip()
        action = (row.get("Action") or "").upper().strip()
        amount_str = (row.get("Amount") or "0").replace(',', '')
        status = row.get("Status") or ""
        order_time_str = row.get("Order Time") or ""
        
        if sym and order_time_str and "Filled" in status:
            try:
                qty = float(amount_str)
                price_str = status.split("Filled at $")[-1].replace(",", "").strip()
                price = float(price_str)
            except Exception as e:
                print(f"Error parsing order quantity/price for {sym}: {e}")
                continue
                
            clean_time = order_time_str.split(" ET ")[0] if " ET " in order_time_str else order_time_str
            date_str = order_time_str.split(" ET ")[-1] if " ET " in order_time_str else ""
            try:
                dt_obj = datetime.strptime(f"{clean_time} {date_str}", "%I:%M:%S %p %b-%d-%Y")
                iso_time = dt_obj.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            except Exception as e:
                iso_time = order_time_str
                
            trades.append({
                "account": "Rollover IRA *5513", # Orders are for Rollover IRA
                "symbol": sym,
                "action": action,
                "units": qty,
                "price": price,
                "trade_date": iso_time
            })
            
    return trades

def main():
    print("Loading clean baseline cache...")
    cache = load_backup_cache()
    
    print("Parsing Monday May 18 trades...")
    may18_trades = parse_may18_trades()
    print(f"Loaded {len(may18_trades)} trades from May 18.")
    
    print("Parsing Tuesday May 19 and Wednesday May 20 trades from dropzone activities (using T-1 trade dates)...")
    may19_may20_trades = parse_may19_may20_trades()
    print(f"Loaded {len(may19_may20_trades)} trades from May 19-20.")
    
    print("Parsing Thursday May 21 trades from dropzone filled orders...")
    may21_trades = parse_may21_trades()
    print(f"Loaded {len(may21_trades)} trades from May 21.")
    
    # Combine all this week's trades
    all_new_trades = may18_trades + may19_may20_trades + may21_trades
    print(f"Total new trades this week: {len(all_new_trades)}")
    
    # Merge into cache
    merged_count = 0
    for t in all_new_trades:
        account = t["account"]
        
        if account not in cache:
            cache[account] = {"activities": [], "positions": [], "closed_positions": []}
            
        activity_id = f"ATP-{t['symbol']}-{t['trade_date']}-{t['units']}-{t['action']}".replace(":", "").replace(" ", "-")
        
        existing_ids = {a["id"] for a in cache[account]["activities"] if "id" in a}
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
        merged_count += 1
        
    print(f"Merged {merged_count} new activities into the cache.")
    
    # Sort activities descending (newest first)
    for account in cache:
        cache[account]["activities"].sort(key=lambda x: x.get("trade_date", ""), reverse=True)
        
    # Overwrite caches
    print(f"Writing updated cache to {cache_path}...")
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2)
        
    print(f"Writing updated backend cache to {backend_cache_path}...")
    os.makedirs(os.path.dirname(backend_cache_path), exist_ok=True)
    with open(backend_cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2)
        
    print(f"Writing updated backup to {backup_path}...")
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2)
        
    # Generate tradezella-import-this-week.csv
    print("Generating TradeZella import CSV...")
    trades_to_export = []
    
    for t in all_new_trades:
        # Exclude Health Savings Account from TradeZella export entirely to avoid Ethereum short trades
        if t["account"] != "Rollover IRA *5513":
            continue
            
        dt = datetime.strptime(t["trade_date"], "%Y-%m-%dT%H:%M:%S.000Z")
        trades_to_export.append({
            "Account Name": t["account"],
            "Date&Time": "",
            "Date": dt.strftime("%m/%d/%Y"),
            "Time": dt.strftime("%H:%M:%S"),
            "Symbol": t["symbol"],
            "Buy/Sell": t["action"].capitalize(),
            "Quantity": t["units"],
            "Price": t["price"],
            "Spread": "Stock",
            "Expiration": "",
            "Strike": "",
            "Call/Put": "",
            "Commission": 0,
            "Fees": 0,
            "_dt": dt
        })
        
    # Sort chronologically ascending
    trades_to_export.sort(key=lambda x: (x["_dt"], x["Symbol"], 0 if x["Buy/Sell"].lower() == "buy" else 1))
    
    for row in trades_to_export:
        del row["_dt"]
        
    tz_headers = ["Account Name", "Date&Time", "Date", "Time", "Symbol", "Buy/Sell", "Quantity", "Price", "Spread", "Expiration", "Strike", "Call/Put", "Commission", "Fees"]
    
    # Define all target export files
    # Normalize paths to use forward slashes for reliable replacements
    norm_output = output_csv.replace('\\', '/')
    export_paths = [
        norm_output,  # data/exports/tradezella-import-this-week.csv
        norm_output.replace('tradezella-import-this-week.csv', 'tradezella-import.csv'),  # data/exports/tradezella-import.csv
    ]
    
    print(f"Writing {len(trades_to_export)} trades to exports:")
    for p in export_paths:
        # Convert back to system-native path format
        native_p = os.path.normpath(p)
        os.makedirs(os.path.dirname(native_p), exist_ok=True)
        with open(native_p, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=tz_headers)
            writer.writeheader()
            writer.writerows(trades_to_export)
        print(f"  - {native_p}")

if __name__ == "__main__":
    main()
