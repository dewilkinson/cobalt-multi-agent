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
    from zoneinfo import ZoneInfo
    eastern_tz = ZoneInfo("America/New_York")
    if not t_str:
        return datetime.min.replace(tzinfo=eastern_tz)
    
    if t_str.endswith('Z'):
        try:
            dt = datetime.fromisoformat(t_str.replace('Z', '+00:00'))
            return dt.astimezone(eastern_tz)
        except Exception:
            pass
            
    try:
        if 'T' in t_str:
            if '.' in t_str:
                dt = datetime.strptime(t_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
                return dt.replace(tzinfo=eastern_tz)
            else:
                dt = datetime.strptime(t_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
                return dt.replace(tzinfo=eastern_tz)
        else:
            dt = datetime.fromisoformat(t_str)
            return dt.replace(tzinfo=eastern_tz)
    except Exception:
        return datetime.min.replace(tzinfo=eastern_tz)

def format_price(val):
    # Formats price to match template decimal representation
    val_float = float(val)
    if val_float.is_integer():
        return f"{val_float:.2f}"
    # Keep up to 4 decimal places if it has fractional parts
    str_val = f"{val_float:.4f}"
    if str_val.endswith("00"):
        return f"{val_float:.2f}"
    return str_val.rstrip('0').rstrip('.') if '.' in str_val else str_val

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
                # Fallback matching
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
            # Map into the generic-trade template headers with precise decimal representation
            filtered_trades.append({
                "Open Time": t["open_time"].strftime("%m/%d/%Y %H:%M:%S"),
                "Close Time": t["close_time"].strftime("%m/%d/%Y %H:%M:%S"),
                "Symbol": t["symbol"],
                "Direction": t["direction"],
                "Volume": f"{t['volume']:.2f}",
                "Open Price": format_price(t["open_price"]),
                "Close Price": format_price(t["close_price"]),
                "P&L": f"{t['pnl']:.2f}",
                "Commission": "0.00",
                "Swap": "0.00",
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
        
    print("Step 4: Generating TradingView Pine Script...")
    try:
        import sys
        sys.path.append(os.path.dirname(__file__))
        import generate_tradingview_script
        generate_tradingview_script.main()
    except Exception as e:
        print(f"  - Warning: Failed to generate TradingView script: {e}")

if __name__ == '__main__':
    run_workflow()
