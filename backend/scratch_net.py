import json
d = json.load(open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json'))
acts = d.get('Rollover IRA *5513', {}).get('activities', [])
syms = ['JOBY', 'AAPL', 'MP', 'NVDA', 'QUBT']

for sym in syms:
    buys = sum(float(a['units']) for a in acts if a.get('symbol', {}).get('symbol') == sym and a['type'] == 'BUY')
    sells = sum(float(a['units']) for a in acts if a.get('symbol', {}).get('symbol') == sym and a['type'] == 'SELL')
    print(f'{sym}: Bought {buys}, Sold {sells}, Net {buys - sells}')
