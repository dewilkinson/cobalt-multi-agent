import json
import os

paths = [
    "data/archive/BrokerageCacheDailyBackup.json",
    "data/archive/BrokerageCacheDailyBackup_2026-06-04.json"
]

for p in paths:
    if os.path.exists(p):
        print(f"Checking {p}...")
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        total_acts = 0
        executed_today = 0
        for acct, acct_data in data.items():
            if "activities" in acct_data:
                for act in acct_data["activities"]:
                    total_acts += 1
                    t_date = act.get("trade_date", "") or act.get("time_placed", "")
                    if "2026-06-04" in t_date:
                        executed_today += 1
                        if executed_today <= 5:
                            print(f"  Sample: {acct} | {act.get('type')} | {act.get('symbol')} | {act.get('units')} @ {act.get('price')} | date={t_date} | status={act.get('status')}")
        print(f"  Total activities: {total_acts}, Executed today (2026-06-04): {executed_today}")
    else:
        print(f"{p} does not exist.")
