import csv
import json
import os
from datetime import datetime

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
csv_path = os.path.join(workspace_dir, "data", "archive", "Orders_Rollover_IRA__5513_2026-06-08_125946.csv")
cache_path = os.path.join(workspace_dir, "data", "brokerage_cache.json")

def parse_date(date_str):
    if not date_str:
        return datetime.min
    date_str = date_str.replace("Z", "")
    # Check if format is like 'May-7-2026'
    for fmt in ("%b-%d-%Y", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    # Maybe it has month name and single digit day like May-7-2026
    # strptime %b-%d-%Y should handle it, but let's be safe
    print(f"Warning: Could not parse date '{date_str}'")
    return datetime.min

def parse_csv_trades():
    trades = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("Symbol,Action,Amount"):
            header_idx = i
            break
            
    if header_idx == -1:
        print("Header not found")
        return trades
        
    csv_data = "".join(lines[header_idx:])
    reader = csv.DictReader(csv_data.splitlines())
    
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
                print(f"Error parsing order: {e}")
                continue
                
            trades.append({
                "symbol": sym,
                "action": action,
                "qty": qty,
                "price": price,
                "time": order_time_str
            })
            
    def get_datetime(t):
        clean_time = t["time"].split(" ET ")[0]
        date_str = t["time"].split(" ET ")[-1]
        return datetime.strptime(f"{clean_time} {date_str}", "%I:%M:%S %p %b-%d-%Y")
    
    trades.sort(key=get_datetime)
    return trades

def calculate_intraday_pnl(trades):
    positions = {}
    realized_pnl = 0
    symbols_pnl = {}
    
    for t in trades:
        sym = t["symbol"]
        action = t["action"]
        qty = t["qty"]
        price = t["price"]
        
        if sym not in positions:
            positions[sym] = []
        if sym not in symbols_pnl:
            symbols_pnl[sym] = 0.0
            
        if action == "BUY":
            positions[sym].append((qty, price))
        elif action == "SELL":
            rem_qty = qty
            pnl = 0
            while rem_qty > 0 and positions[sym]:
                b_qty, b_price = positions[sym][0]
                match_qty = min(rem_qty, b_qty)
                pnl += match_qty * (price - b_price)
                rem_qty -= match_qty
                if b_qty == match_qty:
                    positions[sym].pop(0)
                else:
                    positions[sym][0] = (b_qty - match_qty, b_price)
            if rem_qty > 0:
                print(f"Intraday warning: Short sold {rem_qty} shares of {sym} at {price}")
            realized_pnl += pnl
            symbols_pnl[sym] += pnl
            
    print("\n--- Intraday-Only realized PnL (assuming flat start) ---")
    for sym, pnl in symbols_pnl.items():
        print(f"{sym}: ${pnl:.2f}")
    print(f"Total Intraday PnL: ${realized_pnl:.2f}")
    return realized_pnl, positions

def analyze_cache():
    with open(cache_path, 'r', encoding='utf-8') as f:
        cache = json.load(f)
    
    account_id = "Rollover IRA *5513"
    activities = cache[account_id]["activities"]
    
    # Sort all activities chronologically ascending
    all_acts = []
    for a in activities:
        if a.get("status") != "Executed":
            continue
        dt = parse_date(a.get("trade_date"))
        all_acts.append((dt, a))
        
    all_acts.sort(key=lambda x: x[0])
    
    pos = {} # sym -> list of (qty, price, date)
    realized_pnl_june8 = 0
    pnl_by_sym_june8 = {}
    
    for dt, a in all_acts:
        sym_obj = a.get("symbol", {})
        sym = sym_obj.get("symbol", "") if isinstance(sym_obj, dict) else sym_obj
        qty = float(a["units"])
        price = float(a["price"])
        action = a["type"].upper()
        
        is_june8 = (dt.year == 2026 and dt.month == 6 and dt.day == 8)
        
        if sym not in pos:
            pos[sym] = []
        if sym not in pnl_by_sym_june8:
            pnl_by_sym_june8[sym] = 0.0
            
        if action == "BUY":
            pos[sym].append((qty, price, dt))
        elif action == "SELL":
            rem_qty = qty
            pnl = 0
            while rem_qty > 0 and pos[sym]:
                b_qty, b_price, b_date = pos[sym][0]
                match_qty = min(rem_qty, b_qty)
                match_pnl = match_qty * (price - b_price)
                if is_june8:
                    pnl += match_pnl
                rem_qty -= match_qty
                if b_qty == match_qty:
                    pos[sym].pop(0)
                else:
                    pos[sym][0] = (b_qty - match_qty, b_price, b_date)
            if rem_qty > 0:
                # Sold but no buy history in cache
                if is_june8:
                    print(f"FIFO Warning: Selling {rem_qty} shares of {sym} on June 8 without matching buy in cache.")
            if is_june8:
                realized_pnl_june8 += pnl
                pnl_by_sym_june8[sym] += pnl
                
    print("\n--- Full History FIFO PnL Realized on 2026-06-08 ---")
    for sym, pnl in pnl_by_sym_june8.items():
        if pnl != 0:
            print(f"{sym}: ${pnl:.2f}")
    print(f"Total FIFO PnL on June 8: ${realized_pnl_june8:.2f}")
    
    # Let's inspect the GLXY position prior to June 8
    glxy_pos = []
    for dt, a in all_acts:
        sym_obj = a.get("symbol", {})
        sym = sym_obj.get("symbol", "") if isinstance(sym_obj, dict) else sym_obj
        if sym != "GLXY":
            continue
        qty = float(a["units"])
        price = float(a["price"])
        action = a["type"].upper()
        
        if dt < datetime(2026, 6, 8):
            if action == "BUY":
                glxy_pos.append((qty, price, dt))
            elif action == "SELL":
                rem = qty
                while rem > 0 and glxy_pos:
                    bq, bp, bd = glxy_pos[0]
                    mq = min(rem, bq)
                    rem -= mq
                    if bq == mq:
                        glxy_pos.pop(0)
                    else:
                        glxy_pos[0] = (bq - mq, bp, bd)
                        
    print("\n--- GLXY Position going into June 8 ---")
    if not glxy_pos:
        print("None (Flat)")
    else:
        for q, p, d in glxy_pos:
            print(f"  Buy {q} shares at ${p:.4f} on {d.strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    trades = parse_csv_trades()
    print(f"Parsed {len(trades)} trades from CSV.")
    calculate_intraday_pnl(trades)
    analyze_cache()
