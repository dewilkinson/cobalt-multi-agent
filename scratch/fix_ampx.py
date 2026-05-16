import json
p = 'c:/github/cobalt-multi-agent/data/brokerage_cache.json'
with open(p, 'r') as f:
    d = json.load(f)

for act_id, acc_data in d.items():
    acts = acc_data.get('activities', [])
    for a in acts:
        sym_obj = a.get('symbol', {})
        sym = sym_obj.get('symbol', '') if isinstance(sym_obj, dict) else sym_obj
        if sym == 'AMPX':
            date_str = str(a.get('trade_date', a.get('time_placed', '')))
            if '2026-04-30' in date_str:
                qty = a.get('units', a.get('quantity', 0))
                # BUY 300 at 21.33
                if 'BUY' in a.get('type', a.get('action', '')).upper() and qty == 300:
                    a['trade_date'] = '2026-04-30T09:30:00Z'
                # BUY 150 at 21.16
                elif 'BUY' in a.get('type', a.get('action', '')).upper() and qty == 150:
                    a['trade_date'] = '2026-04-30T10:30:00Z'
                # SELL 750 at 20.81
                elif 'SELL' in a.get('type', a.get('action', '')).upper() and qty == 750:
                    a['trade_date'] = '2026-04-30T11:30:00Z'

with open(p, 'w') as f:
    json.dump(d, f, indent=2)
print("Fixed AMPX timestamps.")
