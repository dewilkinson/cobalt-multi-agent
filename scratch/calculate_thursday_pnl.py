import csv
from collections import defaultdict

csv_path = "data/exports/tradezella-import-this-week.csv"

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

thursday_rows = [r for r in rows if r.get("Date") == "05/21/2026"]

# Group by symbol
trades_by_sym = defaultdict(list)
for r in thursday_rows:
    trades_by_sym[r["Symbol"]].append(r)

total_pnl = 0.0

print("P&L Breakdown for Thursday May 21, 2026:")
for sym, group in trades_by_sym.items():
    # FIFO matching
    buys = []
    sells = []
    for r in group:
        action = r["Buy/Sell"].upper()
        qty = float(r["Quantity"])
        price = float(r["Price"])
        if action == "BUY":
            buys.append({"qty": qty, "price": price})
        elif action == "SELL":
            sells.append({"qty": qty, "price": price})
            
    # Match buys and sells
    sym_pnl = 0.0
    buy_idx = 0
    sell_idx = 0
    
    # We copy buys/sells to avoid mutating
    b_pool = [dict(b) for b in buys]
    s_pool = [dict(s) for s in sells]
    
    b_idx = 0
    s_idx = 0
    while b_idx < len(b_pool) and s_idx < len(s_pool):
        b = b_pool[b_idx]
        s = s_pool[s_idx]
        
        match_qty = min(b["qty"], s["qty"])
        pnl = (s["price"] - b["price"]) * match_qty
        sym_pnl += pnl
        
        b["qty"] -= match_qty
        s["qty"] -= match_qty
        
        if b["qty"] <= 0.0001:
            b_idx += 1
        if s["qty"] <= 0.0001:
            s_idx += 1
            
    print(f"  {sym}: ${sym_pnl:,.2f} (Buys: {len(buys)}, Sells: {len(sells)})")
    total_pnl += sym_pnl

print(f"\nTotal Thursday P&L: ${total_pnl:,.2f}")
