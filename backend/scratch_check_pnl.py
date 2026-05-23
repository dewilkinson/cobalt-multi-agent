import sys
import json

sys.path.append('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend')
from src.services.brokerage_cache import BrokerageCache

d = BrokerageCache._load_cache()
acts = d.get('Rollover IRA *5513', {}).get('activities', [])
acts = sorted(acts, key=lambda a: a.get('trade_date', a.get('time_placed', '')))

tax_lots = {}
missing = 0
realized_pnl = 0.0

for act in acts:
    action = act.get('type', act.get('action', 'N/A')).upper()
    status = str(act.get('status', act.get('state', 'Executed'))).upper()
    if action not in ['BUY', 'SELL', 'BOUGHT', 'SOLD', 'BTO', 'STC', 'BTC', 'STO'] or status in ['OPEN', 'PENDING', 'CANCELED', 'REJECTED']: 
        continue
    
    sym_obj = act.get('symbol') or act.get('universal_symbol') or {}
    sym = sym_obj.get('symbol', act.get('symbol')) if isinstance(sym_obj, dict) else sym_obj
    if not sym: continue
    sym_raw = str(sym).upper().replace('-USD', '').replace('*', '')
    qty = float(act.get('units', 0))
    price = float(act.get('price', 0))
    
    if sym_raw not in tax_lots: tax_lots[sym_raw] = []
    
    if action in ['BUY', 'BOUGHT', 'BTO', 'BTC']:
        tax_lots[sym_raw].append({'qty': qty, 'price': price})
    elif action in ['SELL', 'SOLD', 'STC', 'STO']:
        sell_qty_remaining = qty
        qty_matched = 0
        trade_pnl = 0.0
        while sell_qty_remaining > 0.0001 and len(tax_lots[sym_raw]) > 0:
            lot = tax_lots[sym_raw][0]
            if lot['qty'] <= sell_qty_remaining:
                trade_pnl += (price - lot['price']) * lot['qty']
                sell_qty_remaining -= lot['qty']
                qty_matched += lot['qty']
                tax_lots[sym_raw].pop(0)
            else:
                trade_pnl += (price - lot['price']) * sell_qty_remaining
                lot['qty'] -= sell_qty_remaining
                qty_matched += sell_qty_remaining
                sell_qty_remaining = 0
                
        if sell_qty_remaining > 0.0001:
            fallback = 0.0
            for p in d.get('Rollover IRA *5513', {}).get('positions', []):
                if p.get('symbol') == sym_raw:
                    fallback = float(p.get('average_cost') or 0.0)
                    break
            if fallback > 0:
                trade_pnl += (price - fallback) * sell_qty_remaining
                qty_matched += sell_qty_remaining
                sell_qty_remaining = 0
        
        if sell_qty_remaining > 0.0001 and '2026-05-06' in act.get('trade_date', ''):
            missing += 1
            
        if '2026-05-06' in act.get('trade_date', '') and qty_matched > 0:
            print(f"Sold {qty_matched} {sym_raw} at {price} -> PnL: {trade_pnl}")
            realized_pnl += trade_pnl

print('Realized PnL:', realized_pnl)
print('Missing:', missing)
