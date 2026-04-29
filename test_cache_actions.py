import json
with open('c:/github/cobalt-multi-agent/data/brokerage_cache.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)

actions = {}
for account_id, activities in cache.items():
    for act in activities:
        action = act.get('action', act.get('type', 'N/A')).upper()
        actions[action] = actions.get(action, 0) + 1

print(f"Action counts: {actions}")
