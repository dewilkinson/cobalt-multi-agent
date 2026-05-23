import json
with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json', 'r') as f:
    data = json.load(f)
for account, activities in data.items():
    print(f'Account {account}: {len(activities)} activities')
    for act in activities[:5]:
        sym = act.get('symbol', {}).get('symbol') if isinstance(act.get('symbol'), dict) else act.get('symbol')
        print(f"Symbol: {sym}, trade_date: {act.get('trade_date')}, time_placed: {act.get('time_placed')}")
