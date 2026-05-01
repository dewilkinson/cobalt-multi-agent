import json
from datetime import datetime, timedelta, timezone

with open('c:/github/cobalt-multi-agent/data/brokerage_cache.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)

today_dt = datetime.now(timezone.utc)
today_str = today_dt.strftime("%Y-%m-%d")
target_start_str = (today_dt - timedelta(days=7)).strftime("%Y-%m-%d")

print(f"Today: {today_str}, Target: {target_start_str}")

filtered_activities = []
for account_id, activities in cache.items():
    for act in activities:
        placed_time = act.get('trade_date', act.get('time_placed', ''))
        if placed_time:
            date_only = placed_time[:10]
            if target_start_str <= date_only <= today_str:
                filtered_activities.append(act)
            elif date_only > today_str:
                pass # print(f"Future: {date_only}")
            else:
                pass # print(f"Past: {date_only}")

print(f"Filtered count: {len(filtered_activities)}")
