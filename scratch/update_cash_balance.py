import json
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"

# 1. Update Markdown Reports
md_paths = [
    "c:/github/obsidian-vault/Journals/Daily_Trading_Report_2026-06-10.md",
    "c:/github/obsidian-vault/Journals/Daily Reports/Daily_PostMortem_2026-06-10.md",
    os.path.join(workspace_dir, "data", "reports", "performance", "Daily_PostMortem_2026-06-10.md")
]

for path in md_paths:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace balance
        content = content.replace("Closing Balance: $100,541.12 (Based on Single-Day PNL)", "Closing Balance: $87,731.34 (Actual Cash Balance)")
        content = content.replace("Closing Balance: $100,541.12", "Closing Balance: $87,731.34")
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated cash balance in MD: {path}")

# 2. Update JSON Caches
json_paths = [
    os.path.join(workspace_dir, "data", "brokerage_cache.json"),
    os.path.join(workspace_dir, "backend", "data", "brokerage_cache.json"),
    os.path.join(workspace_dir, "data", "archive", "BrokerageCacheDailyBackup.json"),
    os.path.join(workspace_dir, "data", "archive", "BrokerageCacheDailyBackup_2026-06-10.json")
]

account_id = "Rollover IRA *5513"
for path in json_paths:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            cache = json.load(f)
            
        if account_id in cache:
            positions = cache[account_id].get("positions", [])
            for p in positions:
                if p.get("symbol") in ["Cash (SPAXX)", "SPAXX"]:
                    p["quantity"] = 87731.34
            
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2)
        print(f"Updated cash position in JSON: {path}")
