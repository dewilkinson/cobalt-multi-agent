import json
import os
import sys
from datetime import datetime

def get_trend_value(trends, timeframe):
    if not trends or timeframe not in trends:
        return 0.0
    t_str = trends[timeframe]
    if t_str == 'Strong Bullish': return 1.0
    if t_str == 'Bullish': return 0.6
    if t_str == 'Weak Bullish': return 0.2
    if t_str == 'Weak Bearish': return -0.2
    if t_str == 'Bearish': return -0.6
    if t_str == 'Strong Bearish': return -1.0
    if t_str == 'Accumulation': return 0.0
    return 0.0

def total_to_grade(total):
    if total >= 0.90: return "S"
    if total >= 0.75: return "A"
    if total >= 0.60: return "B"
    if total >= 0.45: return "C"
    if total >= 0.30: return "D"
    return "F"

def main():
    # Paths to directories
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    # Try backend/data first, then fallback to root data/
    strike_list_path = os.path.join(base_dir, "backend", "data", "STRIKE_LIST.json")
    if not os.path.exists(strike_list_path):
        strike_list_path = os.path.join(base_dir, "data", "STRIKE_LIST.json")
        
    trends_cache_path = os.path.join(base_dir, "backend", "data", "trends_cache.json")
        
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
        candidates = data.get("strike_list", [])
        
    if not candidates:
        print("Warning: No candidates found in STRIKE_LIST.json.")
        
    # Load trends cache
    trends_cache = {}
    if os.path.exists(trends_cache_path):
        try:
            with open(trends_cache_path, "r", encoding="utf-8") as f:
                trends_cache = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load trends cache: {e}")

    # Build merged candidates
    merged_candidates = []
    for c in candidates:
        sym = c.get("symbol")
        if not sym:
            continue
        sym_key = sym.upper().strip()
        cache_entry = trends_cache.get(sym_key) or trends_cache.get(sym_key.lower()) or {}
        
        merged_candidates.append({
            "symbol": sym_key,
            "tier": c.get("tier", "").upper().strip(),
            "sortino": cache_entry.get("sortino") if cache_entry.get("sortino") is not None else c.get("sortino", 0.0),
            "pd_zone": cache_entry.get("pd_zone") if cache_entry.get("pd_zone") is not None else c.get("pd_zone", 0.0),
            "rvol": cache_entry.get("rvol") if cache_entry.get("rvol") is not None else c.get("rvol", 1.0),
            "vwap_state": cache_entry.get("vwap_state") if cache_entry.get("vwap_state") is not None else c.get("vwap_state", 0.0),
            "trends": cache_entry.get("trends", {})
        })

    # Define timeframe profiles
    profiles = {
        "day": {
            "trend_timeframe": "15m",
            "is_sortino_enabled": False
        },
        "swing_low": {
            "trend_timeframe": "1h",
            "is_sortino_enabled": False
        },
        "swing_med": {
            "trend_timeframe": "4h",
            "is_sortino_enabled": True
        },
        "hold": {
            "trend_timeframe": "1d",
            "is_sortino_enabled": True
        }
    }
    
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
            
    now = datetime.now()
    time_str_file = now.strftime("%H:%M:%S")
    if not session_ts:
        date_str = now.strftime("%Y-%m-%d")
        time_str_name = now.strftime("%H-%M-%S")
        session_ts = f"{date_str}_{time_str_name}"

    files_written = []

    # Export for each timeframe profile
    for profile_name, prof_config in profiles.items():
        trend_tf = prof_config["trend_timeframe"]
        is_sortino_enabled = prof_config["is_sortino_enabled"]
        
        # Calculate scores and assign grades for all candidates
        profile_candidates_data = []
        symbol_score_map = {}
        
        for c in merged_candidates:
            # 1. Trend Score
            trend_val = get_trend_value(c["trends"], trend_tf)
            trend_score = abs(trend_val)
            
            # 2. Zone Score
            is_bullish = trend_val >= 0.0
            zone_val = float(c["pd_zone"])
            adjusted_zone = -zone_val if is_bullish else zone_val
            zone_score = max(0.0, min(1.0, adjusted_zone))
            
            # 3. RVOL Score
            rvol_val = float(c["rvol"])
            rvol_score = max(0.0, min(1.0, (rvol_val - 0.5) / 1.5))
            
            # 4. VWAP Score
            vwap_val = float(c["vwap_state"])
            vwap_score = 0.0
            if 0.1 <= vwap_val <= 0.5:
                vwap_score = 1.0
            elif vwap_val > 0.5:
                vwap_score = max(0.0, 1.0 - (vwap_val - 0.5) / 0.3)
            elif vwap_val > 0.0:
                vwap_score = vwap_val / 0.1
                
            # 5. Sortino Score
            sortino_val = float(c["sortino"])
            sortino_score = max(0.0, min(1.0, sortino_val / 1.5))
            
            # Total score calculation
            if is_sortino_enabled:
                total_score = (trend_score * 0.30) + (zone_score * 0.30) + (rvol_score * 0.15) + (vwap_score * 0.15) + (sortino_score * 0.10)
            else:
                total_score = (trend_score * 0.35) + (zone_score * 0.35) + (rvol_score * 0.15) + (vwap_score * 0.15)
                
            grade = total_to_grade(total_score)
            
            profile_candidates_data.append({
                "symbol": c["symbol"],
                "tier": c["tier"],
                "score": total_score,
                "grade": grade
            })
            symbol_score_map[c["symbol"]] = total_score

        # Calculate statistical distribution of scores for this profile
        scores = [item["score"] for item in profile_candidates_data]
        if len(scores) > 1:
            mean_score = sum(scores) / len(scores)
            variance = sum((x - mean_score) ** 2 for x in scores) / len(scores)
            std_score = variance ** 0.5
        else:
            mean_score = sum(scores) / len(scores) if scores else 0.0
            std_score = 0.0
            
        if std_score > 0.01:
            high_prob_threshold = mean_score + 0.5 * std_score
            thresh_desc = f"Confidence >= {high_prob_threshold:.2f} (Mean {mean_score:.2f} + 0.5*Std {std_score:.2f})"
        else:
            high_prob_threshold = mean_score
            thresh_desc = f"Confidence >= {high_prob_threshold:.2f} (Mean)"

        # Populate watchlists categorized by tier and grade
        watchlists = {
            "ALL": {"S": [], "A": [], "B": [], "C": [], "D": [], "F": []},
            "SHIELD": {"S": [], "A": [], "B": []},
            "SNIPER": {"S": [], "A": [], "B": []},
            "SWORD": {"S": [], "A": [], "B": []}
        }
        
        for item in profile_candidates_data:
            sym = item["symbol"]
            grade = item["grade"]
            tier = item["tier"]
            
            if grade in watchlists["ALL"]:
                watchlists["ALL"][grade].append(sym)
                
            if grade in ["S", "A", "B"]:
                if tier in watchlists:
                    watchlists[tier][grade].append(sym)

        # Sort watchlists
        for tier in watchlists:
            for grade in watchlists[tier]:
                watchlists[tier][grade] = sorted(list(set(watchlists[tier][grade])))

        # Write files for this profile
        for tier, grades_dict in watchlists.items():
            if tier == "ALL":
                filename_dated = f"scanner_watchlist_all_{profile_name}_{session_ts}.txt"
                filename_static = f"scanner_watchlist_all_{profile_name}.txt"
            else:
                filename_dated = f"watchlist_{tier.lower()}_{profile_name}_{session_ts}.txt"
                filename_static = f"watchlist_{tier.lower()}_{profile_name}.txt"
                
            file_path_dated = os.path.join(exports_dir, filename_dated)
            file_path_static = os.path.join(exports_dir, filename_static)
            
            total_symbols = sum(len(syms) for syms in grades_dict.values())
            
            try:
                for file_path in [file_path_dated, file_path_static]:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(f"# Timeframe Profile: {profile_name.upper()}\n")
                        f.write(f"# Timestamp: {time_str_file}\n")
                        f.write(f"# Statistical Threshold: {thresh_desc}\n\n")
                        
                        grades_to_write = ["S", "A", "B", "C", "D", "F"] if tier == "ALL" else ["S", "A", "B"]
                        
                        high_prob_symbols = []
                        general_dict = {g: [] for g in grades_to_write}
                        
                        for grade in grades_to_write:
                            symbols = grades_dict.get(grade, [])
                            for sym in symbols:
                                score = symbol_score_map.get(sym, 0.0)
                                if score >= high_prob_threshold:
                                    high_prob_symbols.append((sym, score))
                                else:
                                    general_dict[grade].append(sym)
                                    
                        high_prob_symbols.sort(key=lambda x: -x[1])
                        
                        grade_ranges = {
                            "S": "(0.90 - 1.00)",
                            "A": "(0.75 - 0.89)",
                            "B": "(0.60 - 0.74)",
                            "C": "(0.45 - 0.59)",
                            "D": "(0.30 - 0.44)",
                            "F": "(< 0.30)"
                        }
                        
                        if high_prob_symbols:
                            f.write(f"### HIGH PROBABILITY SETUPS (>= {high_prob_threshold:.2f})\n")
                            for sym, score in high_prob_symbols:
                                f.write(f"{sym}\n")
                            f.write("\n")
                            
                        has_general = any(len(syms) > 0 for syms in general_dict.values())
                        if has_general:
                            if high_prob_symbols:
                                f.write("### GENERAL SETUPS\n")
                            for grade in grades_to_write:
                                symbols = general_dict.get(grade, [])
                                if symbols:
                                    f.write(f"### GRADE {grade} {grade_ranges.get(grade, '')}\n")
                                    for sym in symbols:
                                        f.write(f"{sym}\n")
                                        
                files_written.append((f"{tier} ({profile_name.upper()})", file_path_dated, total_symbols))
            except Exception as e:
                print(f"Error writing watchlists for {tier} - {profile_name}: {e}")

    # Print summary
    print("\nWatchlist Export Summary:")
    print("=" * 70)
    for group_desc, path, count in files_written:
        print(f"Group: {group_desc:<22} | Symbols: {count:<4} | Path: {path}")
    print("=" * 70)
    print("Export completed successfully. These files are ready to be imported into TradingView.")

if __name__ == "__main__":
    main()
