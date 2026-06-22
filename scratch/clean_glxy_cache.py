import json
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
cache_paths = [
    os.path.join(workspace_dir, "data", "brokerage_cache.json"),
    os.path.join(workspace_dir, "backend", "data", "brokerage_cache.json"),
    os.path.join(workspace_dir, "data", "archive", "BrokerageCacheDailyBackup.json"),
    os.path.join(workspace_dir, "data", "archive", "BrokerageCacheDailyBackup_2026-06-10.json")
]

def clean_cache_file(path):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
        
    print(f"Cleaning {path}...")
    with open(path, 'r', encoding='utf-8') as f:
        cache = json.load(f)
        
    account_id = "Rollover IRA *5513"
    if account_id not in cache:
        print(f"Account {account_id} not found in {path}")
        return
        
    activities = cache[account_id].get("activities", [])
    
    # Filter out GLXY activities on May 7th
    filtered_activities = []
    removed_count = 0
    
    for a in activities:
        sym_obj = a.get("symbol", {})
        sym = sym_obj.get("symbol", "") if isinstance(sym_obj, dict) else sym_obj
        date_str = a.get("trade_date", "")
        
        is_glxy_may7 = (sym == "GLXY") and ("May-7" in date_str or "2026-05-07" in date_str)
        
        if is_glxy_may7:
            removed_count += 1
        else:
            filtered_activities.append(a)
            
    cache[account_id]["activities"] = filtered_activities
    
    # Save a backup of the original file
    backup_path = path + ".bak"
    with open(backup_path, 'w', encoding='utf-8') as f:
        # Load again to write original raw JSON
        f.write(open(path, 'r', encoding='utf-8').read())
        
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2)
        
    print(f"Removed {removed_count} GLXY May 7th activities from {path}. Backup saved to {backup_path}")

def main():
    for path in cache_paths:
        clean_cache_file(path)

if __name__ == "__main__":
    main()
