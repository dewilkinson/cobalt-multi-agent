import json
file = 'c:/github/cobalt-multi-agent/data/brokerage_cache.json'
with open(file, 'r') as f: data = json.load(f)
acts = data['Rollover IRA *5513']['activities']
for a in acts:
    sym = a.get('symbol', {})
    if isinstance(sym, dict): sym = sym.get('symbol', '')
    if sym == 'INTC' and a.get('type') == 'SELL' and a.get('status') == 'Open':
        a['status'] = 'Executed'
        a['price'] = 98.0517
    elif sym == 'RIOT' and a.get('type') == 'SELL' and a.get('status') == 'Open':
        a['status'] = 'Executed'
        a['price'] = 19.401
with open(file, 'w') as f: json.dump(data, f, indent=2)
