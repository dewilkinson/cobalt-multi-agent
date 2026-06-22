import os
import json
from datetime import datetime

files_to_check = {
    "backend_strike_list": "backend/data/STRIKE_LIST.json",
    "backend_scanner_strike_list": "backend/data/SCANNER_STRIKE_LIST.json",
    "backend_shield_combat_list": "backend/data/SHIELD_COMBAT_LIST.json",
    "backend_scanner_combat_list": "backend/data/SCANNER_COMBAT_LIST.json",
    "root_strike_list": "data/STRIKE_LIST.json",
    "root_scanner_strike_list": "data/SCANNER_STRIKE_LIST.json",
    "obsidian_strike_res_state": "C:/github/obsidian-vault/_cobalt/01_Transit/Buckets/STRIKE_RES_state.json",
    "obsidian_scanner_res_state": "C:/github/obsidian-vault/_cobalt/01_Transit/Buckets/SCANNER_RES_state.json",
}

print("=== SCANNER FILE INSPECTION ===")
for name, path in files_to_check.items():
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        print(f"{name} ({path}): NOT FOUND")
        continue
        
    mtime = os.path.getmtime(abs_path)
    mtime_dt = datetime.fromtimestamp(mtime).isoformat()
    size = os.path.getsize(abs_path)
    
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if isinstance(data, list):
            count = len(data)
            summary = f"Array of {count} items"
        elif isinstance(data, dict):
            candidates = data.get("candidates", []) or data.get("strike_list", [])
            count = len(candidates)
            pulse_mode = data.get("pulse_mode", "N/A")
            summary = f"Dict with {count} candidates (pulse_mode: {pulse_mode})"
        else:
            summary = "Unknown format"
            
        print(f"{name} ({path}): FOUND | Size: {size} B | Modified: {mtime_dt} | Contents: {summary}")
    except Exception as e:
        print(f"{name} ({path}): ERROR reading - {e}")
