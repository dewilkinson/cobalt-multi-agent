import json
with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)

for account_id, activities in cache.items():
    for act in activities[:10]:
        time = act.get('trade_date', act.get('time_placed'))
        sym = ''
        if 'symbol' in act and act['symbol'] and isinstance(act['symbol'], dict) and 'symbol' in act['symbol']:
            sym = act['symbol']['symbol']
        print(f"Sym: {sym}, Time: {time}")
