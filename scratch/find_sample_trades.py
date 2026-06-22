import json

with open("scratch/snaptrade_raw_activities.json", "r", encoding="utf-8") as f:
    data = json.load(f)

trades = []
for act in data:
    # Check if this is a buy/sell trade
    if act.get("type") in ["BUY", "SELL"] or act.get("action") in ["BUY", "SELL"]:
        trades.append(act)

print(f"Found {len(trades)} trade activities.")
if trades:
    print("Sample Trade 1:")
    print(json.dumps(trades[0], indent=2))
    if len(trades) > 1:
        print("\nSample Trade 2:")
        print(json.dumps(trades[1], indent=2))
