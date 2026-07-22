import csv
from collections import defaultdict

rows = list(csv.DictReader(open('data/exports/tradezella-import.csv', encoding='utf-8')))

multipliers = {
    "/MCL": 100.0,
    "/MGC": 10.0,
    "/MNK": 2.0,
    "/MES": 5.0,
    "/MNQ": 2.0,
    "/MYM": 0.5,
    "/M2K": 5.0,
    "/SIL": 1000.0,
}

inventory = defaultdict(list) # sym -> [(qty, price)]
realized_pnl = 0.0
trades_closed = 0

for r in rows:
    sym = r["Symbol"]
    action = r["Buy/Sell"].upper()
    qty = float(r["Quantity"])
    price = float(r["Price"])
    mult = multipliers.get(sym, 1.0)
    
    if action == "BUY":
        # Match against short inventory or add to long inventory
        rem_qty = qty
        while rem_qty > 0 and inventory[sym] and inventory[sym][0][0] < 0: # short pos
            short_qty, short_price = inventory[sym][0]
            matched_qty = min(rem_qty, abs(short_qty))
            pnl = (short_price - price) * matched_qty * mult
            realized_pnl += pnl
            trades_closed += 1
            rem_qty -= matched_qty
            if abs(short_qty) > matched_qty:
                inventory[sym][0] = (short_qty + matched_qty, short_price)
            else:
                inventory[sym].pop(0)
        if rem_qty > 0:
            inventory[sym].append((rem_qty, price))
            
    elif action == "SELL":
        # Match against long inventory or add to short inventory
        rem_qty = qty
        while rem_qty > 0 and inventory[sym] and inventory[sym][0][0] > 0: # long pos
            long_qty, long_price = inventory[sym][0]
            matched_qty = min(rem_qty, long_qty)
            pnl = (price - long_price) * matched_qty * mult
            realized_pnl += pnl
            trades_closed += 1
            rem_qty -= matched_qty
            if long_qty > matched_qty:
                inventory[sym][0] = (long_qty - matched_qty, long_price)
            else:
                inventory[sym].pop(0)
        if rem_qty > 0:
            inventory[sym].append((-rem_qty, price))

print(f"Total July 21 Trades Evaluated: {len(rows)}")
print(f"Realized PnL Today: ${realized_pnl:,.2f}")
