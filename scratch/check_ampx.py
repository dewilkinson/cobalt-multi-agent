import json
d = json.load(open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json'))
for act_id, acc_data in d.items():
    acts = acc_data.get('activities', [])
    ampx_acts = [a for a in acts if (isinstance(a.get('symbol'), dict) and a.get('symbol').get('symbol') == 'AMPX') or a.get('symbol') == 'AMPX']
    if ampx_acts:
        print(f'=== Account: {act_id} ===')
        for a in reversed(ampx_acts): # print oldest first
            date_str = str(a.get('trade_date', a.get('time_placed', '')))[:19]
            action = a.get('type', a.get('action', 'N/A')).upper()
            qty = a.get('units', a.get('quantity', 0))
            price = a.get('price', 0)
            print(f'{date_str} | {action} AMPX | Qty: {qty} | Price: {price}')
