import json
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
cache_path = os.path.join(workspace_dir, "data", "brokerage_cache.json")

with open(cache_path, 'r', encoding='utf-8') as f:
    cache = json.load(f)

print("Active Positions by Account:")
for acc, data in cache.items():
    print(f"\nAccount: {acc}")
    positions = data.get("positions", [])
    if not positions:
        print("  No positions.")
    else:
        for pos in positions:
            print(f"  Symbol: {pos.get('symbol')} | Qty: {pos.get('quantity')} | Value: {pos.get('total_cost')}")
