import json
d = json.load(open('c:/github/cobalt-multi-agent/data/brokerage_cache.json'))
for acct, data in d.items():
    if 'positions' in data:
        data['positions'] = [p for p in data['positions'] if 'Cash' in p.get('symbol', '') or 'SPAXX' in p.get('symbol', '')]

with open('c:/github/cobalt-multi-agent/data/brokerage_cache.json', 'w') as f:
    json.dump(d, f, indent=2)
print("Cleared open positions except cash.")
