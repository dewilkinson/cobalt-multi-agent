import os
import json

def test_scanner():
    scanner_res_content = {"candidates": [], "pulse_mode": "Automated Pulse"}
    sword_path = os.path.join(os.getcwd(), "data", "SCANNER_COMBAT_LIST.json")
    
    try:
        if os.path.exists(sword_path):
            with open(sword_path, encoding="utf-8") as f:
                data = json.load(f)
                cands = data.get("candidates", []) or data.get("combat_list", [])
                for c in cands:
                    if "tier" not in c:
                        c["tier"] = "SWORD"
                scanner_res_content["candidates"].extend(cands)
                scanner_res_content["pulse_mode"] = data.get("pulse_mode", "Sortino Sniper Scanner")
        print(f"Sword loaded: {len(scanner_res_content['candidates'])}")
    except Exception as e:
        print(f"Failed to load Sword data: {e}")
        
    shield_path = os.path.join(os.getcwd(), "data", "SHIELD_COMBAT_LIST.json")
    try:
        if os.path.exists(shield_path):
            with open(shield_path, encoding="utf-8") as sf:
                s_data = json.load(sf)
                s_list = s_data.get("combat_list", []) or s_data.get("candidates", [])
                for c in s_list:
                    c["tier"] = "SHIELD"
                scanner_res_content["candidates"].extend(s_list)
        print(f"Total after shield loaded: {len(scanner_res_content['candidates'])}")
    except Exception as e:
        print(f"Failed to load Shield data: {e}")
        
    print("Done")

test_scanner()
