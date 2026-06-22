import json
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
cache_path = os.path.join(workspace_dir, "data", "brokerage_cache.json")

with open(cache_path, 'r', encoding='utf-8') as f:
    cache = json.load(f)

for acc, data in cache.items():
    print(f"Account: {acc}")
    print(f"Keys: {list(data.keys())}")
    if "positions" in data:
        print(f"Positions Count: {len(data['positions'])}")
    if "closed_positions" in data:
        print(f"Closed Positions Count: {len(data['closed_positions'])}")
    # Print a tiny sample of positions
    if data.get("positions"):
        print(f"Sample Position: {data['positions'][0]}")
