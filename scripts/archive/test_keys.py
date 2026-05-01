import json
with open('c:/github/cobalt-multi-agent/data/brokerage_cache.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)

for account_id, activities in cache.items():
    print(activities[0].keys())
    print("symbol:", activities[0].get('symbol'))
    print("universal_symbol:", activities[0].get('universal_symbol'))
    break
