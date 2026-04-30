import json
with open('data/brokerage_cache.json', 'r') as f:
    cache = json.load(f)
print(list(cache.keys()))
