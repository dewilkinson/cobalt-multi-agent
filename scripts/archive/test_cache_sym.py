import json
with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)

for account_id, activities in cache.items():
    print(f"Type: {type(activities[0].get('symbol'))}")
    print(activities[0].get('symbol'))
    break
