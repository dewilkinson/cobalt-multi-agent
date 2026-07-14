import os
from dotenv import load_dotenv
# Load default root .env first
load_dotenv()
# Load backend/.env to resolve vault path and other configurations
backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
if os.path.exists(backend_env):
    load_dotenv(backend_env, override=True)
import sys
# Add backend to sys.path to allow importing backend tools
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
from src.tools.scanner import load_strategy_constraints

import json
import requests
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np

def fetch_av_data():
    api_key = os.getenv("FMP_API_KEY", "")
    base_url = "https://financialmodelingprep.com/stable"
    
    strat_config = load_strategy_constraints("default")
    price_min = strat_config["price_min"]
    
    data_dict = {
        "top_gainers": [],
        "top_losers": [],
        "most_actively_traded": []
    }
    
    endpoints = {
        "top_gainers": f"{base_url}/biggest-gainers?apikey={api_key}",
        "top_losers": f"{base_url}/biggest-losers?apikey={api_key}",
        "most_actively_traded": f"{base_url}/most-actives?apikey={api_key}"
    }
    
    for key, url in endpoints.items():
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                # Remap FMP keys to what the AV script expects
                remapped = []
                for item in data:
                    price = float(item.get("price", 0.0))
                    if price < price_min:
                        continue
                        
                    remapped.append({
                        "ticker": item.get("symbol", ""),
                        "price": str(price),
                        "change_percentage": f"{item.get('changesPercentage', 0)}%",
                        "volume": str(item.get("volume", "0"))
                    })
                data_dict[key] = remapped
        except Exception as e:
            print(f"Error fetching {key} from FMP: {e}")
            
    return data_dict

def load_scanner_list(date_str, base_dir):
    scanner_map = {}
    
    # 1. Load from scan_list_{date_str}.json
    scanner_path = os.path.join(base_dir, "data", "archive", f"scan_list_{date_str}.json")
    if os.path.exists(scanner_path):
        try:
            with open(scanner_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                history = data.get("history", [])
                for item in history:
                    # Filter: Only include symbols active on the given date_str (today)
                    last_seen = item.get("last_seen", "")
                    first_added = item.get("first_added", "")
                    if last_seen.startswith(date_str) or first_added.startswith(date_str):
                        sym = item.get("symbol", "").upper().strip()
                        if sym:
                            if sym not in scanner_map:
                                scanner_map[sym] = {
                                    "grade": "N/A",
                                    "sortino": None,
                                    "tiers": set()
                                }
                            if item.get("grade"):
                                scanner_map[sym]["grade"] = item.get("grade")
                            if item.get("sortino") is not None:
                                scanner_map[sym]["sortino"] = item.get("sortino")
                            t = item.get("tier", "N/A").upper().strip()
                            if t and t != "N/A":
                                scanner_map[sym]["tiers"].add(t)
        except Exception as e:
            print(f"Error loading daily scanner archive: {e}")

    # 2. Load from STRIKE_LIST.json and SCANNER_STRIKE_LIST.json in both root data and backend data
    strike_list_paths = [
        os.path.join(base_dir, "data", "STRIKE_LIST.json"),
        os.path.join(base_dir, "backend", "data", "STRIKE_LIST.json"),
        os.path.join(base_dir, "data", "SCANNER_STRIKE_LIST.json"),
        os.path.join(base_dir, "backend", "data", "SCANNER_STRIKE_LIST.json")
    ]
    
    for path in strike_list_paths:
        if os.path.exists(path):
            try:
                # Check file timestamp to ensure it was modified/updated today
                updated_today = False
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                if isinstance(data, dict):
                    updated_at = data.get("updated_at", "")
                    if updated_at.startswith(date_str):
                        updated_today = True
                
                # Fallback to file system mtime if no updated_at key is found
                if not updated_today:
                    mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")
                    if mtime == date_str:
                        updated_today = True
                        
                if updated_today:
                    candidates = []
                    if isinstance(data, list):
                        candidates = data
                    elif isinstance(data, dict):
                        candidates = data.get("candidates", []) or data.get("strike_list", [])
                    
                    for item in candidates:
                        if not isinstance(item, dict):
                            continue
                        sym = item.get("symbol", "").upper().strip()
                        if sym:
                            if sym not in scanner_map:
                                scanner_map[sym] = {
                                    "grade": "N/A",
                                    "sortino": None,
                                    "tiers": set()
                                }
                            if item.get("grade"):
                                scanner_map[sym]["grade"] = item.get("grade")
                            if item.get("sortino") is not None:
                                scanner_map[sym]["sortino"] = item.get("sortino")
                            t = item.get("tier", "N/A").upper().strip()
                            if t and t != "N/A":
                                scanner_map[sym]["tiers"].add(t)
            except Exception as e:
                print(f"Error loading strike list from {path}: {e}")
                
    return scanner_map

def calculate_gappers(tickers):
    if not tickers: return []
    try:
        df = yf.download(tickers, period="5d", interval="1d", group_by='ticker', progress=False)
        gaps = []
        for t in tickers:
            try:
                t_df = df if len(tickers) == 1 else df.get(t)
                if t_df is None or t_df.empty: continue
                
                t_df = t_df.dropna(subset=['Open', 'Close'])
                if len(t_df) >= 2:
                    prev_close = float(t_df['Close'].iloc[-2])
                    today_open = float(t_df['Open'].iloc[-1])
                    if prev_close > 0:
                        gap_pct = ((today_open - prev_close) / prev_close) * 100.0
                        gaps.append({"symbol": t, "gap_pct": gap_pct})
            except Exception:
                continue
        gaps.sort(key=lambda x: x["gap_pct"], reverse=True)
        return gaps
    except Exception as e:
        print(f"Error calculating gaps: {e}")
        return []

def calculate_sortino(prices_series, target_return=0.0):
    returns = prices_series.pct_change().dropna()
    if len(returns) < 2: return 0.0
    mean_return = returns.mean() * 252
    downside_returns = returns[returns < target_return]
    if len(downside_returns) == 0: return 99.0
    downside_deviation = np.sqrt((downside_returns**2).mean()) * np.sqrt(252)
    return float(mean_return / downside_deviation) if downside_deviation > 0 else 99.0

def analyze_missed_gainers(missed_tickers, scanner_map=None):
    if not missed_tickers: return []
    if scanner_map is None:
        scanner_map = {}
        
    analysis_results = []
    
def analyze_missed_gainers(missed_tickers, scanner_map):
    """
    Analyzes missed gainers and evaluates why they failed constraints for each active strategy profile (Sword, Shield, Sniper).
    """
    if not missed_tickers:
        return []
        
    analysis_results = []
    print(f"Analyzing {len(missed_tickers)} missed gainers...")
    
    # Filter out tickers that have cached Sortino values to avoid redundant downloads
    tickers_to_download = []
    for sym in missed_tickers:
        if sym in scanner_map and scanner_map[sym].get("sortino") is not None:
            continue
        tickers_to_download.append(sym)

    hist_data = None
    if tickers_to_download:
        try:
            # Fetch historical data for Sortino calculation
            hist_data = yf.download(tickers_to_download, period="1y", interval="1d", group_by='ticker', progress=False)
        except Exception as e:
            print(f"Failed to fetch history for missed gainers: {e}")
            hist_data = None

    for sym in missed_tickers:
        try:
            ticker_obj = yf.Ticker(sym)
            info = ticker_obj.info
            q_type = info.get('quoteType', 'EQUITY')
            price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose', 0)
            cap = info.get('marketCap', 0)
            float_shares = info.get('floatShares', 0)
            vol = info.get('regularMarketVolume') or info.get('volume', 0)
            
            # Sortino Calculation
            sortino = 0.0
            if sym in scanner_map and scanner_map[sym].get("sortino") is not None:
                sortino = scanner_map[sym]["sortino"]
            elif hist_data is not None:
                try:
                    t_df = hist_data if len(tickers_to_download) == 1 else hist_data.get(sym)
                    if t_df is not None and not t_df.empty:
                        prices = t_df['Close'].dropna()
                        sortino = calculate_sortino(prices)
                except Exception:
                    pass
            
            strat_results = {}
            for s_name in ["sword", "shield", "default"]:
                s_config = load_strategy_constraints(s_name)
                s_reasons = []
                
                p_min = s_config["price_min"]
                p_max = s_config.get("price_max") or float('inf')
                if p_max == 0: p_max = float('inf')
                
                c_min = s_config["market_cap_min"]
                c_max = s_config.get("market_cap_max") or float('inf')
                if c_max == 0: c_max = float('inf')
                
                f_min = s_config["float_min"]
                f_max = s_config.get("float_max") or float('inf')
                if f_max == 0: f_max = float('inf')
                
                # Apply tolerance for market cap
                t_pct = s_config.get("market_cap_tolerance_pct", 0.0)
                p_f_max = s_config.get("float_premium_max", 0)
                eff_c_min = c_min
                if t_pct > 0 and p_f_max > 0 and float_shares <= p_f_max:
                    eff_c_min = c_min * (1.0 - (t_pct / 100.0))
                
                # 1. Price Check
                if price < p_min or price > p_max:
                    p_max_str = f"${p_max:.2f}" if p_max != float('inf') else "No Limit"
                    s_reasons.append(f"Price (${price}) out of bounds (${p_min}-{p_max_str})")
                    
                # 2. Market Cap Check
                if q_type != "ETF":
                    if cap < eff_c_min or cap > c_max:
                        c_max_str = f"${c_max/1e6:.0f}M" if c_max != float('inf') else "No Limit"
                        eff_c_min_str = f"${eff_c_min/1e6:.1f}M" if eff_c_min != c_min else f"${c_min/1e6:.0f}M"
                        s_reasons.append(f"Cap (${cap/1e6:.1f}M) out of bounds ({eff_c_min_str}-{c_max_str})")
                        
                # 3. Float Check
                if q_type != "ETF":
                    if float_shares < f_min or float_shares > f_max:
                        float_max_str = f"{f_max/1e6:.0f}M" if f_max != float('inf') else "No Limit"
                        s_reasons.append(f"Float ({float_shares/1e6:.1f}M) out of bounds ({f_min/1e6:.0f}M-{float_max_str})")
                
                # 4. Volume Check
                v_hurdle = s_config["volume_hurdle"]
                if vol < v_hurdle:
                    s_reasons.append(f"Volume ({vol}) below minimum ({v_hurdle})")
                    
                # 5. Sortino Check
                enable_sortino = os.environ.get("SCANNER_ENABLE_SORTINO", "false").lower() == "true"
                s_min = s_config["sortino_hurdle"]
                if enable_sortino and sortino < s_min:
                    s_reasons.append(f"Sortino ({sortino:.2f}) below minimum ({s_min})")
                    
                disp_name = s_name.upper() if s_name != "default" else "SNIPER"
                if not s_reasons:
                    strat_results[disp_name] = "Passed static constraints"
                else:
                    strat_results[disp_name] = f"Failed ({'; '.join(s_reasons)})"
                    
            reasons_parts = [f"**{k}**: {v}" for k, v in strat_results.items()]
            analysis_results.append({"symbol": sym, "reasons": ["<br>".join(reasons_parts)]})
            
        except Exception as e:
            analysis_results.append({"symbol": sym, "reasons": [f"Failed to fetch data: {e}"]})
            
    return analysis_results

def format_strategy_cell(sym, strategy, scanner_map):
    if sym in scanner_map:
        info = scanner_map[sym]
        tiers = info.get("tiers", set())
        matched = False
        for t in tiers:
            if strategy.upper() in t or t in strategy.upper():
                matched = True
                break
        if matched:
            return f"✅ Yes ({info.get('grade', 'N/A')})"
    return "❌ No"

def render_miss_reasons_table(tickers, scanner_map, missed_analysis_map):
    missed_tickers = [t for t in tickers if t and t not in scanner_map]
    if not missed_tickers:
        return []
    
    table_lines = [
        "| Symbol | Reasons for Rejection / Miss |",
        "| :--- | :--- |"
    ]
    for sym in missed_tickers:
        reasons = missed_analysis_map.get(sym, ["Pending analysis..."])
        reasons_clean = "<br>".join([r.strip() for r in reasons])
        table_lines.append(f"| {sym} | {reasons_clean} |")
    
    return ["", "### Scan Miss Reasons", ""] + table_lines + [""]

def load_watchlist_map(date_str):
    watchlist_map = {}
    try:
        import sqlite3
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        db_path = os.path.join(base_dir, "data", "watchlists.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            rows = cursor.execute("SELECT symbol, color FROM watchlists WHERE date = ?", (date_str,)).fetchall()
            for sym, color in rows:
                sym = sym.upper().strip()
                if sym:
                    if sym not in watchlist_map:
                        watchlist_map[sym] = set()
                    watchlist_map[sym].add(color)
            conn.close()
    except Exception as e:
        print(f"Error loading watchlist map: {e}")
    return watchlist_map

def format_watchlist_cell(sym, target_color, watchlist_map):
    if sym in watchlist_map:
        colors = watchlist_map[sym]
        for c in colors:
            if target_color.lower() in c.lower() or c.lower() in target_color.lower():
                return "✅ Yes"
    return "❌ No"

def build_markdown(date_str, av_data, gappers, scanner_map, watchlist_map, missed_analysis_map):
    lines = [
        f"# Daily Scanner Review: {date_str}",
        "",
        "This report is generated automatically by sweeping the market using the AlphaVantage API and cross-referencing with your Cobalt Multiagent scanner hits.",
        ""
    ]
    
    # 1. Top Gainers
    lines.extend(["## Top 10 Market Gainers", ""])
    lines.extend(["| Symbol | Price | Change % | Volume | Sword | Shield | Sortino Sniper | Primary<br>(Cyan) | Potential<br>(Pink) | Special<br>(Gold) | Rejected<br>(Red) | Scanner<br>(All) |",
                  "| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"])
    for item in av_data.get("top_gainers", [])[:10]:
        sym = item.get("ticker", "")
        price = item.get("price", "0")
        change = item.get("change_percentage", "0")
        vol = item.get("volume", "0")
        
        sword_s = format_strategy_cell(sym, "SWORD", scanner_map)
        shield_s = format_strategy_cell(sym, "SHIELD", scanner_map)
        sniper_s = format_strategy_cell(sym, "SNIPER", scanner_map)
        
        cyan_s = format_watchlist_cell(sym, "Cyan", watchlist_map)
        pink_s = format_watchlist_cell(sym, "Pink", watchlist_map)
        gold_s = format_watchlist_cell(sym, "Gold", watchlist_map)
        red_s = format_watchlist_cell(sym, "Red", watchlist_map)
        scan_wl_s = format_watchlist_cell(sym, "Scanner Watchlist", watchlist_map)
        
        lines.append(f"| {sym} | ${price} | {change} | {vol} | {sword_s} | {shield_s} | {sniper_s} | {cyan_s} | {pink_s} | {gold_s} | {red_s} | {scan_wl_s} |")
    lines.append("")
    
    gainer_tickers = [item.get("ticker", "") for item in av_data.get("top_gainers", [])[:10]]
    lines.extend(render_miss_reasons_table(gainer_tickers, scanner_map, missed_analysis_map))
    
    # 2. Top Losers
    lines.extend(["## Top 10 Market Losers", ""])
    lines.extend(["| Symbol | Price | Change % | Volume | Sword | Shield | Sortino Sniper | Primary<br>(Cyan) | Potential<br>(Pink) | Special<br>(Gold) | Rejected<br>(Red) | Scanner<br>(All) |",
                  "| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"])
    for item in av_data.get("top_losers", [])[:10]:
        sym = item.get("ticker", "")
        price = item.get("price", "0")
        change = item.get("change_percentage", "0")
        vol = item.get("volume", "0")
        
        sword_s = format_strategy_cell(sym, "SWORD", scanner_map)
        shield_s = format_strategy_cell(sym, "SHIELD", scanner_map)
        sniper_s = format_strategy_cell(sym, "SNIPER", scanner_map)
        
        cyan_s = format_watchlist_cell(sym, "Cyan", watchlist_map)
        pink_s = format_watchlist_cell(sym, "Pink", watchlist_map)
        gold_s = format_watchlist_cell(sym, "Gold", watchlist_map)
        red_s = format_watchlist_cell(sym, "Red", watchlist_map)
        scan_wl_s = format_watchlist_cell(sym, "Scanner Watchlist", watchlist_map)
        
        lines.append(f"| {sym} | ${price} | {change} | {vol} | {sword_s} | {shield_s} | {sniper_s} | {cyan_s} | {pink_s} | {gold_s} | {red_s} | {scan_wl_s} |")
    lines.append("")
    
    loser_tickers = [item.get("ticker", "") for item in av_data.get("top_losers", [])[:10]]
    lines.extend(render_miss_reasons_table(loser_tickers, scanner_map, missed_analysis_map))
    
    # 3. Most Actively Traded
    lines.extend(["## Top 10 Most Actively Traded (Volume)", ""])
    lines.extend(["| Symbol | Price | Change % | Volume | Sword | Shield | Sortino Sniper | Primary<br>(Cyan) | Potential<br>(Pink) | Special<br>(Gold) | Rejected<br>(Red) | Scanner<br>(All) |",
                  "| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"])
    for item in av_data.get("most_actively_traded", [])[:10]:
        sym = item.get("ticker", "")
        price = item.get("price", "0")
        change = item.get("change_percentage", "0")
        vol = item.get("volume", "0")
        
        sword_s = format_strategy_cell(sym, "SWORD", scanner_map)
        shield_s = format_strategy_cell(sym, "SHIELD", scanner_map)
        sniper_s = format_strategy_cell(sym, "SNIPER", scanner_map)
        
        cyan_s = format_watchlist_cell(sym, "Cyan", watchlist_map)
        pink_s = format_watchlist_cell(sym, "Pink", watchlist_map)
        gold_s = format_watchlist_cell(sym, "Gold", watchlist_map)
        red_s = format_watchlist_cell(sym, "Red", watchlist_map)
        scan_wl_s = format_watchlist_cell(sym, "Scanner Watchlist", watchlist_map)
        
        lines.append(f"| {sym} | ${price} | {change} | {vol} | {sword_s} | {shield_s} | {sniper_s} | {cyan_s} | {pink_s} | {gold_s} | {red_s} | {scan_wl_s} |")
    lines.append("")
    
    active_tickers = [item.get("ticker", "") for item in av_data.get("most_actively_traded", [])[:10]]
    lines.extend(render_miss_reasons_table(active_tickers, scanner_map, missed_analysis_map))
    
    # 4. Top Gappers
    lines.extend(["## Top 10 Gappers", "*(Calculated from the open vs previous close of the top gainers/actives)*", ""])
    lines.extend(["| Symbol | Pre-Market Gap % | Sword | Shield | Sortino Sniper | Primary<br>(Cyan) | Potential<br>(Pink) | Special<br>(Gold) | Rejected<br>(Red) | Scanner<br>(All) |",
                  "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"])
    for item in gappers[:10]:
        sym = item["symbol"]
        gap = item["gap_pct"]
        sword_s = format_strategy_cell(sym, "SWORD", scanner_map)
        shield_s = format_strategy_cell(sym, "SHIELD", scanner_map)
        sniper_s = format_strategy_cell(sym, "SNIPER", scanner_map)
        
        cyan_s = format_watchlist_cell(sym, "Cyan", watchlist_map)
        pink_s = format_watchlist_cell(sym, "Pink", watchlist_map)
        gold_s = format_watchlist_cell(sym, "Gold", watchlist_map)
        red_s = format_watchlist_cell(sym, "Red", watchlist_map)
        scan_wl_s = format_watchlist_cell(sym, "Scanner Watchlist", watchlist_map)
        
        lines.append(f"| {sym} | {gap:.2f}% | {sword_s} | {shield_s} | {sniper_s} | {cyan_s} | {pink_s} | {gold_s} | {red_s} | {scan_wl_s} |")
    lines.append("")
            
    return "\n".join(lines)

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # Allow passing date as --date YYYY-MM-DD
    date_str = None
    mode = "light"
    for arg in sys.argv:
        if arg.startswith("--date="):
            date_str = arg.split("=")[1]
        elif arg == "--date" and len(sys.argv) > sys.argv.index(arg) + 1:
            date_str = sys.argv[sys.argv.index(arg) + 1]
        elif arg.startswith("--mode="):
            mode = arg.split("=")[1].lower()
            
    if not date_str:
        eastern = ZoneInfo("America/New_York")
        date_str = datetime.now(eastern).strftime("%Y-%m-%d")
        
    os.environ["VLI_REPORT_DATE"] = date_str
    
    print(f"Generating Daily Scanner Review for {date_str}...")
    
    av_data = fetch_av_data()
    if not av_data:
        print("Failed to fetch AlphaVantage data. Exiting.")
        sys.exit(1)
        
    scanner_map = load_scanner_list(date_str, base_dir)
    
    # Identify missed tickers across all three top 10 lists
    top_gainers = av_data.get("top_gainers", [])[:10]
    top_losers = av_data.get("top_losers", [])[:10]
    most_active = av_data.get("most_actively_traded", [])[:10]
    
    # Fetch actual volumes from yfinance since FMP biggest-gainers/losers/actives doesn't include volume in FMP response
    all_top_tickers = list(set([item["ticker"] for item in top_gainers + top_losers + most_active if item.get("ticker")]))
    if all_top_tickers:
        print(f"Fetching actual volumes from yfinance for {len(all_top_tickers)} tickers on {date_str}...")
        try:
            df = yf.download(all_top_tickers, period="5d", interval="1d", group_by='ticker', progress=False)
            for item in top_gainers + top_losers + most_active:
                sym = item.get("ticker")
                try:
                    t_df = df if len(all_top_tickers) == 1 else df.get(sym)
                    if t_df is not None and not t_df.empty:
                        # Drop NaN index values if any, and convert to string
                        valid_df = t_df.dropna(subset=['Volume'])
                        valid_df.index = pd.to_datetime(valid_df.index).strftime("%Y-%m-%d")
                        if date_str in valid_df.index:
                            vol = valid_df.loc[date_str, 'Volume']
                            if isinstance(vol, pd.Series):
                                vol = vol.iloc[-1]
                            item["volume"] = f"{int(vol):,}"
                except Exception as e:
                    print(f"Error getting volume for {sym}: {e}")
        except Exception as e:
            print(f"Failed to fetch volumes from yfinance: {e}")
            
    # Save top 10 lists to the watchlist database
    try:
        from src.services.watchlist_db import save_watchlist_entries
        db_entries = []
        imported_at_str = datetime.now().isoformat()
        
        for item in top_gainers:
            sym = item.get("ticker", "").upper().strip()
            if sym:
                db_entries.append((date_str, "Top 10 Market Gainers", sym, "AlphaVantage Sweeper", imported_at_str))
                
        for item in top_losers:
            sym = item.get("ticker", "").upper().strip()
            if sym:
                db_entries.append((date_str, "Top 10 Market Losers", sym, "AlphaVantage Sweeper", imported_at_str))
                
        for item in most_active:
            sym = item.get("ticker", "").upper().strip()
            if sym:
                db_entries.append((date_str, "Top 10 Most Actively Traded (Volume)", sym, "AlphaVantage Sweeper", imported_at_str))
                
        if db_entries:
            save_watchlist_entries(db_entries)
            print(f"Added {len(db_entries)} top 10 market leaders to watchlist database.")
    except Exception as dbe:
        print(f"Failed to save top 10 leaders to watchlist database: {dbe}")
    
    missed_gainers = [g.get("ticker", "") for g in top_gainers if g.get("ticker") and g.get("ticker") not in scanner_map]
    missed_losers = [l.get("ticker", "") for l in top_losers if l.get("ticker") and l.get("ticker") not in scanner_map]
    missed_actives = [a.get("ticker", "") for a in most_active if a.get("ticker") and a.get("ticker") not in scanner_map]
    
    all_missed = list(set(missed_gainers + missed_losers + missed_actives))
    
    # Pool tickers to calculate gaps
    gapper_pool = set()
    for item in av_data.get("top_gainers", [])[:20]: gapper_pool.add(item.get("ticker"))
    for item in av_data.get("most_actively_traded", [])[:20]: gapper_pool.add(item.get("ticker"))
    gapper_pool = list(filter(None, list(gapper_pool)))
    
    print(f"Calculating gaps for {len(gapper_pool)} tickers...")
    gappers = calculate_gappers(gapper_pool)
    
    # Run analysis on all unique missed tickers
    print(f"Running miss analysis on {len(all_missed)} total unique missed symbols...")
    missed_results = analyze_missed_gainers(all_missed, scanner_map)
    missed_analysis_map = {item["symbol"]: item["reasons"] for item in missed_results}
    
    watchlist_map = load_watchlist_map(date_str)
    md_content = build_markdown(date_str, av_data, gappers, scanner_map, watchlist_map, missed_analysis_map)
    
    # Check if today's post-mortem report exists to combine it
    post_mortem_content = ""
    post_mortem_path = os.path.join(base_dir, "data", "reports", "performance", f"Daily_PostMortem_{date_str}.md")
    
    if not os.path.exists(post_mortem_path):
        if mode == "full":
            print(f"Post-mortem report not found at {post_mortem_path}. Triggering real-time post-mortem synthesis...")
            try:
                import asyncio
                from src.server.app import _background_synthesis_task
                asyncio.run(_background_synthesis_task(
                    text="Analyze today's executed trades and generate a detailed Daily Trading Report post-mortem.",
                    image=None,
                    direct_mode=False,
                    reporter_llm_type="reasoning",
                    vli_llm_type="core",
                    thread_id=f"POSTMORTEM_{date_str}",
                    silent=True,
                    thinking_mode=True
                ))
            except Exception as e:
                print(f"Failed to generate post-mortem report in real-time: {e}")
        else:
            print(f"Post-mortem report not found at {post_mortem_path}. Skipping real-time post-mortem synthesis in LIGHT mode.")

    if os.path.exists(post_mortem_path):
        try:
            with open(post_mortem_path, "r", encoding="utf-8") as f:
                post_mortem_content = f.read()
            print(f"Loaded post-mortem report for {date_str} to combine.")
        except Exception as e:
            print(f"Failed to read post-mortem report: {e}")
            
    if post_mortem_content:
        try:
            from src.services.historical_reports import combine_reports, sync_combined_report_files
            combined_content = combine_reports(post_mortem_content, md_content, date_str=date_str)
            # Sync reports across cache and vault files
            sync_combined_report_files(date_str, combined_content, has_market_report=True)
            print("Successfully compiled and synchronized combined reports.")
        except Exception as e:
            print(f"Failed to combine/sync reports: {e}")
    else:
        # Save just the scanner review report
        out_dir = os.path.join(base_dir, "data", "archive", "daily_scanner_reviews")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"Daily_Scanner_Review_{date_str}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Saved Daily Scanner Review without post-mortem to {out_path}")

if __name__ == "__main__":
    main()

