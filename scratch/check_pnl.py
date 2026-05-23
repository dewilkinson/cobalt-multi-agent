import json

d = json.load(open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json'))
for act_id, acc_data in d.items():
    acts = acc_data.get('activities', [])
    y_acts = [a for a in acts if '2026-05-12' in str(a.get('trade_date', a.get('time_placed', '')))]
    if y_acts:
        print(f'=== Account: {act_id} ===')
        for a in y_acts:
            sym_obj = a.get('symbol', {})
            sym = sym_obj.get('symbol', '') if isinstance(sym_obj, dict) else sym_obj
            date_str = str(a.get('trade_date', a.get('time_placed', '')))[:19]
            action = a.get('type', a.get('action', 'N/A')).upper()
            qty = a.get('units', a.get('quantity', 0))
            price = a.get('price', 0)
            print(f"{date_str} | {action} {sym} | Qty: {qty} | Price: {price}")
