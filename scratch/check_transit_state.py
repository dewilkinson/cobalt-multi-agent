import os
import sys

# Add backend src to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from src.config.vli import get_vli_path

def main():
    print(f"Current Working Directory: {os.getcwd()}")
    
    # Check get_vli_path resolving
    try:
        transit_path = get_vli_path(os.path.join("01_Transit", "Buckets", "STRIKE_RES_state.json"))
        print(f"Resolved STRIKE_RES_state.json path: {transit_path}")
        print(f"  Exists: {os.path.exists(transit_path)}")
        if os.path.exists(transit_path):
            print(f"  Size: {os.path.getsize(transit_path)} bytes")
            with open(transit_path, 'r', encoding='utf-8') as f:
                import json
                data = json.load(f)
                print(f"  Pulse Mode: {data.get('pulse_mode')}")
                print(f"  Total Pulsed: {data.get('total_pulsed')}")
                print(f"  Number of candidates: {len(data.get('candidates', []))}")
    except Exception as e:
        print(f"Error checking get_vli_path: {e}")
        
    # Check STRIKE_LIST.json in data/
    paths = [
        os.path.abspath(os.path.join("data", "STRIKE_LIST.json")),
        os.path.abspath(os.path.join("backend", "data", "STRIKE_LIST.json")),
        os.path.abspath(os.path.join("data", "SCANNER_STRIKE_LIST.json")),
        os.path.abspath(os.path.join("backend", "data", "SCANNER_STRIKE_LIST.json")),
    ]
    
    print("\nChecking file paths:")
    for path in paths:
        exists = os.path.exists(path)
        print(f"Path: {path}")
        print(f"  Exists: {exists}")
        if exists:
            print(f"  Size: {os.path.getsize(path)} bytes")
            with open(path, 'r', encoding='utf-8') as f:
                try:
                    import json
                    d = json.load(f)
                    print(f"    Keys: {list(d.keys())}")
                    if 'candidates' in d:
                        print(f"    Candidates count: {len(d['candidates'])}")
                    if 'strike_list' in d:
                        print(f"    Strike list count: {len(d['strike_list'])}")
                except Exception as e:
                    print(f"    Error reading JSON: {e}")

if __name__ == "__main__":
    main()
