import os

path = r'c:\github\cobalt-multi-agent\backend\src\tools\scanner.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

out_lines = []
in_fn = False
fn_started = False
for line in lines:
    if line.startswith('async def clear_scanner_cache() -> str:'):
        in_fn = True
        fn_started = True
        out_lines.append(line)
        out_lines.append('    """Purges the entire scanner combat list and transit state cache."""\n')
        out_lines.append('    import os\n')
        out_lines.append('    from src.config.vli import get_vli_path\n')
        out_lines.append('    import json\n')
        out_lines.append('    combat_list_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "SCANNER_COMBAT_LIST.json"))\n')
        out_lines.append('    shield_combat_list_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "SHIELD_COMBAT_LIST.json"))\n')
        out_lines.append('    transit_path = get_vli_path(os.path.join("01_Transit", "Buckets", "SCANNER_RES_state.json"))\n')
        out_lines.append('    shield_transit_path = get_vli_path(os.path.join("01_Transit", "Buckets", "SHIELD_RES_state.json"))\n')
        out_lines.append('    purged = []\n')
        out_lines.append('    for path, name in [(combat_list_path, "SCANNER_COMBAT_LIST.json"), (shield_combat_list_path, "SHIELD_COMBAT_LIST.json")]:\n')
        out_lines.append('        try:\n')
        out_lines.append('            with open(path, "w", encoding="utf-8") as f: json.dump([], f)\n')
        out_lines.append('            purged.append(name)\n')
        out_lines.append('        except: pass\n')
        out_lines.append('    for path, name in [(transit_path, "SCANNER_RES_state.json"), (shield_transit_path, "SHIELD_RES_state.json")]:\n')
        out_lines.append('        try:\n')
        out_lines.append('            with open(path, "w", encoding="utf-8") as f: json.dump({"pulse_mode": "CLEARED", "total_pulsed": 0, "candidates_passed": 0, "candidates": []}, f)\n')
        out_lines.append('            purged.append(name)\n')
        out_lines.append('        except: pass\n')
        out_lines.append('    if not purged: return "Scanner cache is already empty."\n')
        out_lines.append('    return f"Successfully purged scanner cache files: {str(purged)}"\n\n')
        continue
    
    if in_fn:
        # Check if we hit the next function or the end
        if line.startswith('@') or line.startswith('def ') or line.startswith('async def'):
            if fn_started and len(line.strip()) > 0 and not line.startswith(' '):
                in_fn = False
                out_lines.append(line)
    else:
        out_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(out_lines)

print("Fixed clear_scanner_cache")
