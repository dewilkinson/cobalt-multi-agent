import json
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
cache_path = os.path.join(workspace_dir, "data", "brokerage_cache.json")

with open(cache_path, 'r', encoding='utf-8') as f:
    cache = json.load(f)

account_id = "Rollover IRA *5513"
activities = cache[account_id]["activities"]

june7_acts = []
for a in activities:
    date_str = a.get("trade_date", "")
    if "2026-06-07" in date_str or "Jun-7" in date_str or "June-7" in date_str:
        june7_acts.append(a)

print(f"Number of activities on June 7: {len(june7_acts)}")
for a in june7_acts:
    print(a)
