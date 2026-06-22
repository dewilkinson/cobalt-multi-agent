import json
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
cache_path = os.path.join(workspace_dir, "data", "brokerage_cache.json")

with open(cache_path, 'r', encoding='utf-8') as f:
    cache = json.load(f)

account_id = "Rollover IRA *5513"
activities = cache[account_id]["activities"]

aapl_acts = []
for a in activities:
    sym_obj = a.get("symbol", {})
    sym = sym_obj.get("symbol", "") if isinstance(sym_obj, dict) else sym_obj
    if sym == "AAPL":
        aapl_acts.append(a)

aapl_acts.sort(key=lambda x: x.get("trade_date", ""))

print("AAPL Activities in cache:")
for a in aapl_acts:
    print(f"Date: {a.get('trade_date')} | Type: {a.get('type')} | Units: {a.get('units')} | Price: {a.get('price')} | ID: {a.get('id')}")
