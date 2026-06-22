import json

backup_path = "data/archive/BrokerageCacheDailyBackup_0.json"

with open(backup_path, 'r', encoding='utf-8') as f:
    cache = json.load(f)

print("BrokerageCacheDailyBackup_0.json summary:")
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
    # Print the most recent 10 dates
    print(f"Most recent 10 dates: {sorted_dates[-10:]}")
