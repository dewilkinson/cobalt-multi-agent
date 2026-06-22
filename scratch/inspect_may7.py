import json
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
cache_path = os.path.join(workspace_dir, "data", "brokerage_cache.json")

with open(cache_path, 'r', encoding='utf-8') as f:
    cache = json.load(f)

account_id = "Rollover IRA *5513"
activities = cache[account_id]["activities"]

may7_acts = []
for a in activities:
    date_str = a.get("trade_date", "")
    if "May-7" in date_str or "2026-05-07" in date_str:
        may7_acts.append(a)

print(f"Number of activities on May 7: {len(may7_acts)}")
for a in may7_acts:
    sym_obj = a.get("symbol", {})
    sym = sym_obj.get("symbol", "") if isinstance(sym_obj, dict) else sym_obj
    print(f"Date: {a.get('trade_date')} | Sym: {sym} | Type: {a.get('type')} | Units: {a.get('units')} | Price: {a.get('price')} | ID: {a.get('id')}")
