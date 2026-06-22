import json
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
cache_path = os.path.join(workspace_dir, "data", "brokerage_cache.json")

with open(cache_path, 'r', encoding='utf-8') as f:
    cache = json.load(f)

account_id = "Rollover IRA *5513"
activities = cache[account_id]["activities"]

for a in activities:
    if "HIST-GLXY-May-7-2026" in a.get("id", ""):
        print(json.dumps(a, indent=2))
