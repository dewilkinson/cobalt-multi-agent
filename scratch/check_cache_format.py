import json

with open("data/archive/BrokerageCacheDailyBackup_0.json", 'r', encoding='utf-8') as f:
    cache = json.load(f)

# Find an activity in Rollover IRA
ira_acts = cache.get("Rollover IRA *5513", {}).get("activities", [])
print(f"Total Rollover IRA activities: {len(ira_acts)}")
if ira_acts:
    print("Sample IRA Activity:")
    print(json.dumps(ira_acts[0], indent=2))
    print("\nSecond Sample IRA Activity:")
    print(json.dumps(ira_acts[1], indent=2))
