import json
d = json.load(open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json'))
acts = d.get('Rollover IRA *5513', {}).get('activities', [])
acts = sorted(acts, key=lambda a: a.get('trade_date', a.get('time_placed', '')))

tax_lots = {}
orphaned = []
for act in acts:
    action = act.get('type', act.get('action', '')).upper()
    sym = act.get('symbol', {}).get('symbol')
    if not sym: continue
    sym = sym.upper()
    qty = float(act.get('units', 0))
    status = str(act.get('status', 'Executed')).upper()
    
    if action not in ['BUY', 'SELL'] or status in ['OPEN', 'PENDING', 'CANCELED']: continue
    
    if action == 'BUY':
        if sym not in tax_lots: tax_lots[sym] = []
        tax_lots[sym].append({'qty': qty})
    elif action == 'SELL':
        sell_qty = qty
        while sell_qty > 0.0001 and tax_lots.get(sym, []):
            lot = tax_lots[sym][0]
            if lot['qty'] <= sell_qty:
                sell_qty -= lot['qty']
                tax_lots[sym].pop(0)
            else:
                lot['qty'] -= sell_qty
                sell_qty = 0
        if sell_qty > 0.0001:
            orphaned.append(act)

print([a['id'] for a in orphaned])
