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
    
    # Dynamically load constraints for the default strategy
    strat_config = load_strategy_constraints("default")
        
    PRICE_MIN = strat_config["price_min"]
    PRICE_MAX = strat_config["price_max"]
    CAP_MIN = strat_config["market_cap_min"]
    CAP_MAX = strat_config["market_cap_max"]
    FLOAT_MIN = strat_config["float_min"]
    FLOAT_MAX = strat_config["float_max"]
    SORTINO_MIN = strat_config["sortino_hurdle"]
    VOLUME_MIN = strat_config["volume_hurdle"]

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
        reasons = []
        try:
            ticker_obj = yf.Ticker(sym)
            info = ticker_obj.info
            
            q_type = info.get('quoteType', 'EQUITY')
            
            # 1. Price Check
            price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose', 0)
            if price < PRICE_MIN or price > PRICE_MAX:
                reasons.append(f"**Price (${price})** out of bounds (${PRICE_MIN}-${PRICE_MAX})")
                
            # 2. Market Cap Check
            if q_type != "ETF":
                cap = info.get('marketCap', 0)
                if cap < CAP_MIN or cap > CAP_MAX:
                    reasons.append(f"**Market Cap (${cap/1e6:.1f}M)** out of bounds (${CAP_MIN/1e6:.0f}M-${CAP_MAX/1e6:.0f}M)")
                
            # 3. Float Check
            if q_type != "ETF":
                float_shares = info.get('floatShares', 0)
                if float_shares < FLOAT_MIN or float_shares > FLOAT_MAX:
                    reasons.append(f"**Float ({float_shares/1e6:.1f}M)** out of bounds ({FLOAT_MIN/1e6:.0f}M-{FLOAT_MAX/1e6:.0f}M)")
                
            # 4. Volume Check
            vol = info.get('regularMarketVolume') or info.get('volume', 0)
            if vol < VOLUME_MIN:
                reasons.append(f"**Volume ({vol})** below minimum ({VOLUME_MIN})")
                
            # 5. Sortino Calculation
            sortino = 0.0
            if sym in scanner_map and scanner_map[sym].get("sortino") is not None:
                sortino = scanner_map[sym]["sortino"]
                print(f"Using cached Sortino for {sym}: {sortino}")
            elif hist_data is not None:
                try:
                    t_df = hist_data if len(tickers_to_download) == 1 else hist_data.get(sym)
                    if t_df is not None and not t_df.empty:
                        prices = t_df['Close'].dropna()
                        sortino = calculate_sortino(prices)
                except Exception:
                    pass
                
            enable_sortino = os.environ.get("SCANNER_ENABLE_SORTINO", "false").lower() == "true"
            if enable_sortino:
                if sortino < SORTINO_MIN:
                    reasons.append(f"**Sortino Ratio ({sortino:.2f})** below minimum ({SORTINO_MIN})")
                
            if not reasons:
                reasons.append("Met all constraints (Might have failed LLM Phase 2 or Sentiment Filter).")
                
            analysis_results.append({"symbol": sym, "reasons": reasons})
            
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

def build_markdown(date_str, av_data, gappers, scanner_map, missed_analysis_map):
    lines = [
        f"# Daily Scanner Review: {date_str}",
        "",
        "This report is generated automatically by sweeping the market using the AlphaVantage API and cross-referencing with your Cobalt Multiagent scanner hits.",
        ""
    ]
    
    # 1. Top Gainers
    lines.extend(["## Top 10 Market Gainers", ""])
    lines.extend(["| Symbol | Price | Change % | Volume | Sword | Shield | Sortino Sniper |", "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"])
    for item in av_data.get("top_gainers", [])[:10]:
        sym = item.get("ticker", "")
        price = item.get("price", "0")
        change = item.get("change_percentage", "0")
        vol = item.get("volume", "0")
        sword_s = format_strategy_cell(sym, "SWORD", scanner_map)
        shield_s = format_strategy_cell(sym, "SHIELD", scanner_map)
        sniper_s = format_strategy_cell(sym, "SNIPER", scanner_map)
        lines.append(f"| {sym} | ${price} | {change} | {vol} | {sword_s} | {shield_s} | {sniper_s} |")
    lines.append("")
    
    gainer_tickers = [item.get("ticker", "") for item in av_data.get("top_gainers", [])[:10]]
    lines.extend(render_miss_reasons_table(gainer_tickers, scanner_map, missed_analysis_map))
    
    # 2. Top Losers
    lines.extend(["## Top 10 Market Losers", ""])
    lines.extend(["| Symbol | Price | Change % | Volume | Sword | Shield | Sortino Sniper |", "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"])
    for item in av_data.get("top_losers", [])[:10]:
        sym = item.get("ticker", "")
        price = item.get("price", "0")
        change = item.get("change_percentage", "0")
        vol = item.get("volume", "0")
        sword_s = format_strategy_cell(sym, "SWORD", scanner_map)
        shield_s = format_strategy_cell(sym, "SHIELD", scanner_map)
        sniper_s = format_strategy_cell(sym, "SNIPER", scanner_map)
        lines.append(f"| {sym} | ${price} | {change} | {vol} | {sword_s} | {shield_s} | {sniper_s} |")
    lines.append("")
    
    loser_tickers = [item.get("ticker", "") for item in av_data.get("top_losers", [])[:10]]
    lines.extend(render_miss_reasons_table(loser_tickers, scanner_map, missed_analysis_map))
    
    # 3. Most Actively Traded
    lines.extend(["## Top 10 Most Actively Traded (Volume)", ""])
    lines.extend(["| Symbol | Price | Change % | Volume | Sword | Shield | Sortino Sniper |", "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"])
    for item in av_data.get("most_actively_traded", [])[:10]:
        sym = item.get("ticker", "")
        price = item.get("price", "0")
        change = item.get("change_percentage", "0")
        vol = item.get("volume", "0")
        sword_s = format_strategy_cell(sym, "SWORD", scanner_map)
        shield_s = format_strategy_cell(sym, "SHIELD", scanner_map)
        sniper_s = format_strategy_cell(sym, "SNIPER", scanner_map)
        lines.append(f"| {sym} | ${price} | {change} | {vol} | {sword_s} | {shield_s} | {sniper_s} |")
    lines.append("")
    
    active_tickers = [item.get("ticker", "") for item in av_data.get("most_actively_traded", [])[:10]]
    lines.extend(render_miss_reasons_table(active_tickers, scanner_map, missed_analysis_map))
    
    # 4. Top Gappers
    lines.extend(["## Top 10 Gappers", "*(Calculated from the open vs previous close of the top gainers/actives)*", ""])
    lines.extend(["| Symbol | Pre-Market Gap % | Sword | Shield | Sortino Sniper |", "| :--- | :--- | :--- | :--- | :--- |"])
    for item in gappers[:10]:
        sym = item["symbol"]
        gap = item["gap_pct"]
        sword_s = format_strategy_cell(sym, "SWORD", scanner_map)
        shield_s = format_strategy_cell(sym, "SHIELD", scanner_map)
        sniper_s = format_strategy_cell(sym, "SNIPER", scanner_map)
        lines.append(f"| {sym} | {gap:.2f}% | {sword_s} | {shield_s} | {sniper_s} |")
    lines.append("")
            
    return "\n".join(lines)

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # Allow passing date as --date YYYY-MM-DD
    date_str = None
    for arg in sys.argv:
        if arg.startswith("--date="):
            date_str = arg.split("=")[1]
        elif arg == "--date" and len(sys.argv) > sys.argv.index(arg) + 1:
            date_str = sys.argv[sys.argv.index(arg) + 1]
            
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
    
    md_content = build_markdown(date_str, av_data, gappers, scanner_map, missed_analysis_map)
    
    # Check if today's post-mortem report exists to combine it
    post_mortem_content = ""
    post_mortem_path = os.path.join(base_dir, "data", "reports", "performance", f"Daily_PostMortem_{date_str}.md")
    
    if not os.path.exists(post_mortem_path):
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
                silent=True
            ))
        except Exception as e:
            print(f"Failed to generate post-mortem report in real-time: {e}")

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

