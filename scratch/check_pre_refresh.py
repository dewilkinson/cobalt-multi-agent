import json
import os

path = "data/archive/brokerage_cache_pre_refresh.json"
if not os.path.exists(path):
    print("brokerage_cache_pre_refresh.json not found!")
    exit(1)

with open(path, 'r', encoding='utf-8') as f:
    cache = json.load(f)

print("brokerage_cache_pre_refresh.json summary:")
all_dates = set()
for account, data in cache.items():
    activities = data.get("activities", [])
    print(f"Account: {account} | {len(activities)} activities")
    for act in activities:
        date = act.get("trade_date")
        if date:
            all_dates.add(date[:10])

sorted_dates = sorted(list(all_dates))
print(f"Total unique dates: {len(sorted_dates)}")
if sorted_dates:
    print(f"Date range: {sorted_dates[0]} to {sorted_dates[-1]}")
    # Print the most recent 15 dates
    print(f"Most recent 15 dates: {sorted_dates[-15:]}")
