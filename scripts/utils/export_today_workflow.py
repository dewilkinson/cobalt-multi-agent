import os
import sys
import json
import csv
import shutil
from datetime import datetime

# Add backend to path to import backend services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))
from src.services.brokerage_cache import BrokerageCache

def parse_time(act):
    t_str = act.get('trade_date', '') or act.get('time_placed', '')
    try:
        if 'T' in t_str:
            if '.' in t_str:
                return datetime.strptime(t_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            else:
                return datetime.strptime(t_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
        else:
            return datetime.fromisoformat(t_str)
    except Exception:
        return datetime.min

def run_workflow():
    print("Step 1: Running daily backup cache...")
    try:
        BrokerageCache.backup_cache_daily()
        print("  - Daily backup copy created.")
    except Exception as e:
        print(f"  - Warning during daily backup: {e}")
        
    print("Step 2: Copying current cache to BrokerageCacheDailyBackup.json...")
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cache_file = os.path.join(project_root, "data", "brokerage_cache.json")
    backup_file = os.path.join(project_root, "data", "archive", "BrokerageCacheDailyBackup.json")
    
    if os.path.exists(cache_file):
        shutil.copy2(cache_file, backup_file)
        print(f"  - Successfully copied to {backup_file}")
    else:
        print(f"  - Error: Source cache file not found at {cache_file}")
        return
        
    print("Step 3: Extracting closed trades for TradeZella (Closed Trades template)...")
    target_date = datetime.now().strftime("%Y-%m-%d")
    print(f"  - Target date resolved as: {target_date}")
    
    with open(backup_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    activities = data.get("Rollover IRA *5513", {}).get("activities", [])
    chronological_acts = sorted(activities, key=parse_time)
    
    tax_lots = {}  # symbol -> list of {"qty": float, "price": float, "time": datetime}
    closed_trades = []
    
    for act in chronological_acts:
        action = act.get('type', '').upper()
        status = act.get('status', '').upper()
        if status not in ['EXECUTED', 'FILLED']:
            continue
            
        sym = act.get('symbol', {}).get('symbol') if isinstance(act.get('symbol'), dict) else act.get('symbol')
        if not sym:
            continue
        sym = sym.upper()
        
        qty = float(act.get('units', 0))
        price = float(act.get('price', 0))
        trade_time = parse_time(act)
        
        if action in ["BUY", "BOUGHT", "BTO", "BTC"]:
            if sym not in tax_lots:
                tax_lots[sym] = []
            tax_lots[sym].append({"qty": qty, "price": price, "time": trade_time})
            
        elif action in ["SELL", "SOLD", "STC", "STO"]:
            if sym not in tax_lots:
                tax_lots[sym] = []
                
            sell_qty_remaining = qty
            
            while sell_qty_remaining > 0.0001 and len(tax_lots[sym]) > 0:
                lot = tax_lots[sym][0]
                if lot["qty"] <= sell_qty_remaining:
                    qty_matched = lot["qty"]
                    pnl = (price - lot["price"]) * qty_matched
                    
                    closed_trades.append({
                        "open_time": lot["time"],
                        "close_time": trade_time,
                        "symbol": sym,
                        "direction": "Buy",
                        "volume": qty_matched,
                        "open_price": lot["price"],
                        "close_price": price,
                        "pnl": pnl
                    })
                    
                    sell_qty_remaining -= qty_matched
                    tax_lots[sym].pop(0)
                else:
                    qty_matched = sell_qty_remaining
                    pnl = (price - lot["price"]) * qty_matched
                    
                    closed_trades.append({
                        "open_time": lot["time"],
                        "close_time": trade_time,
                        "symbol": sym,
                        "direction": "Buy",
                        "volume": qty_matched,
                        "open_price": lot["price"],
                        "close_price": price,
                        "pnl": pnl
                    })
                    
                    lot["qty"] -= qty_matched
                    sell_qty_remaining = 0.0
                    
            if sell_qty_remaining > 0.0001:
                # Fallback matching with current sell price (PnL = 0, open_time = close_time)
                closed_trades.append({
                    "open_time": trade_time,
                    "close_time": trade_time,
                    "symbol": sym,
                    "direction": "Buy",
                    "volume": sell_qty_remaining,
                    "open_price": price,
                    "close_price": price,
                    "pnl": 0.0
                })

    # Filter for trades closed today
    filtered_trades = []
    for t in closed_trades:
        close_date_str = t["close_time"].strftime("%Y-%m-%d")
        if close_date_str == target_date:
            # Map into the generic-trade template headers
            filtered_trades.append({
                "Open Time": t["open_time"].strftime("%Y-%m-%d %H:%M:%S"),
                "Close Time": t["close_time"].strftime("%Y-%m-%d %H:%M:%S"),
                "Symbol": t["symbol"],
                "Direction": t["direction"],
                "Volume": int(t["volume"]) if t["volume"].is_integer() else t["volume"],
                "Open Price": round(t["open_price"], 4),
                "Close Price": round(t["close_price"], 4),
                "P&L": round(t["pnl"], 2),
                "Commission": 0.00,
                "Swap": 0.00,
                "Spread": "stock",
                "Currency": "USD"
            })
            
    print(f"  - Matched {len(filtered_trades)} closed trades for {target_date}.")
    
    tz_headers = ["Open Time", "Close Time", "Symbol", "Direction", "Volume", "Open Price", "Close Price", "P&L", "Commission", "Swap", "Spread", "Currency"]
    
    output_path = os.path.join(project_root, "data", "exports", "tradezella-import.csv")
    output_today_path = os.path.join(project_root, "data", "exports", f"tradezella-import-{target_date}.csv")
    
    export_paths = [output_path, output_today_path]
    
    for p in export_paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=tz_headers)
            writer.writeheader()
            writer.writerows(filtered_trades)
        print(f"  - Written to {p}")

if __name__ == '__main__':
    run_workflow()
