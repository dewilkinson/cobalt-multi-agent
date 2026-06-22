import json
import os
from datetime import datetime

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
cache_path = os.path.join(workspace_dir, "data", "brokerage_cache.json")

def parse_date(date_str):
    if not date_str:
        return datetime.min
    date_str = date_str.replace("Z", "")
    for fmt in ("%b-%d-%Y", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    return datetime.min

def verify_positions():
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
    
    positions = {} # symbol -> quantity
    
    for dt, a in all_acts:
        sym_obj = a.get("symbol", {})
        sym = sym_obj.get("symbol", "") if isinstance(sym_obj, dict) else sym_obj
        
        # Ignore cash proxies
        if sym in ["CASH", "FZFXX", "SPAXX", "FCASH", "FDRXX", "Cash (SPAXX)"]:
            continue
            
        qty = float(a["units"])
        price = float(a["price"])
        action = a["type"].upper()
        
        if sym not in positions:
            positions[sym] = 0.0
            
        if action == "BUY":
            positions[sym] += qty
        elif action == "SELL":
            positions[sym] -= qty
            
    # Check for non-zero positions
    open_positions = {}
    for sym, qty in positions.items():
        if abs(qty) > 0.0001:
            open_positions[sym] = qty
            
    print(f"\nTotal unique symbols traded: {len(positions)}")
    print(f"Open positions found: {len(open_positions)}")
    for sym, qty in sorted(open_positions.items()):
        print(f"  {sym}: {qty:.4f} shares")

if __name__ == "__main__":
    verify_positions()
