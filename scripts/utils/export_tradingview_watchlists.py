import json
import os
import sys

def main():
    # Paths to directories
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    # Try backend/data first, then fallback to root data/
    strike_list_path = os.path.join(base_dir, "backend", "data", "STRIKE_LIST.json")
    if not os.path.exists(strike_list_path):
        strike_list_path = os.path.join(base_dir, "data", "STRIKE_LIST.json")
        
    # Always output to root data/exports/ folder
    exports_dir = os.path.join(base_dir, "data", "exports")
    os.makedirs(exports_dir, exist_ok=True)
    
    if not os.path.exists(strike_list_path):
        print(f"Error: STRIKE_LIST.json not found.")
        sys.exit(1)
        
    try:
        with open(strike_list_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading STRIKE_LIST.json: {e}")
        sys.exit(1)
        
    candidates = data.get("candidates", [])
    if not candidates:
        # Check for 'strike_list' fallback key
        candidates = data.get("strike_list", [])
        
    if not candidates:
        print("Warning: No candidates found in STRIKE_LIST.json.")
        
    # Categorize by tier and grade
    watchlists = {
        "ALL": {"S": [], "A": [], "B": []},
        "SHIELD": {"S": [], "A": [], "B": []},
        "SNIPER": {"S": [], "A": [], "B": []},
        "SWORD": {"S": [], "A": [], "B": []}
    }
    
    for c in candidates:
        sym = c.get("symbol")
        if not sym:
            continue
            
        # Export only S, A, and B grades (e.g. S, A+, A, B+, B)
        grade = c.get("grade", "").upper().strip()
        if not (grade.startswith("S") or grade.startswith("A") or grade.startswith("B")):
            continue
            
        tier = c.get("tier", "").upper().strip()
        sym = sym.upper().strip()
        base_grade = grade[0]
        
        watchlists["ALL"][base_grade].append(sym)
        if tier in watchlists:
            watchlists[tier][base_grade].append(sym)
        else:
            print(f"Warning: Unknown tier '{tier}' for symbol '{sym}'")
            
    # Sort all list contents
    for tier in watchlists:
        for grade in watchlists[tier]:
            watchlists[tier][grade] = sorted(list(set(watchlists[tier][grade])))
        
    from datetime import datetime
    now = datetime.now()
    time_str_file = now.strftime("%H:%M:%S")
    
    # Try to load session timestamp
    session_ts = None
    meta_path = os.path.join(base_dir, "backend", "data", ".session_metadata.json")
    if not os.path.exists(meta_path):
        meta_path = os.path.join(base_dir, "data", ".session_metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                session_ts = json.load(f).get("session_timestamp")
        except:
            pass
            
    if not session_ts:
        date_str = now.strftime("%Y-%m-%d")
        time_str_name = now.strftime("%H-%M-%S")
        session_ts = f"{date_str}_{time_str_name}"
    
    # Write watchlists to files
    files_written = {}
    for tier, grades_dict in watchlists.items():
        filename_dated = f"watchlist_{tier.lower()}_{session_ts}.txt"
        filename_static = f"watchlist_{tier.lower()}.txt"
        file_path_dated = os.path.join(exports_dir, filename_dated)
        file_path_static = os.path.join(exports_dir, filename_static)
        
        total_symbols = sum(len(syms) for syms in grades_dict.values())
        
        try:
            for file_path in [file_path_dated, file_path_static]:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"# Timestamp: {time_str_file}\n")
                    for grade in ["S", "A", "B"]:
                        symbols = grades_dict[grade]
                        if symbols:
                            f.write(f"### GRADE {grade}\n")
                            for sym in symbols:
                                f.write(f"{sym}\n")
            files_written[tier] = (file_path_dated, total_symbols)
        except Exception as e:
            print(f"Error writing watchlists for {tier}: {e}")
            
    # Print summary
    print("\nWatchlist Export Summary:")
    print("=" * 60)
    for tier, (path, count) in files_written.items():
        print(f"Watchlist: {tier:<10} | Symbols: {count:<4} | Path: {path}")
    print("=" * 60)
    print("Export completed successfully. These files are ready to be imported into TradingView.")


if __name__ == "__main__":
    main()
