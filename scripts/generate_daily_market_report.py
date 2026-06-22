import os
import sys
import json
import requests
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np

def fetch_av_data():
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "premium")
    url = f"https://www.alphavantage.co/query?function=TOP_GAINERS_LOSERS&apikey={api_key}&entitlement=realtime"
    
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching AlphaVantage data: {e}")
        return {}

def load_scanner_list(date_str, base_dir):
    scanner_path = os.path.join(base_dir, "data", "archive", f"scan_list_{date_str}.json")
    if not os.path.exists(scanner_path):
        return {}
    
    try:
        with open(scanner_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            history = data.get("history", [])
            
            scanner_map = {}
            for item in history:
                sym = item.get("symbol", "").upper()
                if sym:
                    scanner_map[sym] = {
                        "grade": item.get("grade", "N/A"),
                        "tier": item.get("tier", "N/A")
                    }
            return scanner_map
    except Exception as e:
        print(f"Error loading scanner list: {e}")
        return {}

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

def analyze_missed_gainers(missed_tickers):
    if not missed_tickers: return []
    
    analysis_results = []
    
    # Scanner Constraints
    PRICE_MIN, PRICE_MAX = 5.0, 50.0
    CAP_MIN, CAP_MAX = 300_000_000, 2_000_000_000
    FLOAT_MIN, FLOAT_MAX = 20_000_000, 100_000_000
    SORTINO_MIN = 2.0
    VOLUME_MIN = 50000

    print(f"Analyzing {len(missed_tickers)} missed gainers...")
    
    try:
        # Fetch historical data for Sortino
        hist_data = yf.download(missed_tickers, period="1y", interval="1d", group_by='ticker', progress=False)
    except Exception as e:
        print(f"Failed to fetch history for missed gainers: {e}")
        hist_data = None

    for sym in missed_tickers:
        reasons = []
        try:
            ticker_obj = yf.Ticker(sym)
            info = ticker_obj.info
            
            # 1. Price Check
            price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose', 0)
            if price < PRICE_MIN or price > PRICE_MAX:
                reasons.append(f"**Price (${price})** out of bounds (${PRICE_MIN}-${PRICE_MAX})")
                
            # 2. Market Cap Check
            cap = info.get('marketCap', 0)
            if cap < CAP_MIN or cap > CAP_MAX:
                reasons.append(f"**Market Cap (${cap/1e6:.1f}M)** out of bounds (${CAP_MIN/1e6:.0f}M-${CAP_MAX/1e6:.0f}M)")
                
            # 3. Float Check
            float_shares = info.get('floatShares', 0)
            if float_shares < FLOAT_MIN or float_shares > FLOAT_MAX:
                reasons.append(f"**Float ({float_shares/1e6:.1f}M)** out of bounds ({FLOAT_MIN/1e6:.0f}M-{FLOAT_MAX/1e6:.0f}M)")
                
            # 4. Volume Check
            vol = info.get('regularMarketVolume') or info.get('volume', 0)
            if vol < VOLUME_MIN:
                reasons.append(f"**Volume ({vol})** below minimum ({VOLUME_MIN})")
                
            # 5. Sortino Check
            sortino = 0.0
            if hist_data is not None:
                try:
                    t_df = hist_data if len(missed_tickers) == 1 else hist_data.get(sym)
                    if t_df is not None and not t_df.empty:
                        prices = t_df['Close'].dropna()
                        sortino = calculate_sortino(prices)
                except Exception:
                    pass
            
            if sortino < SORTINO_MIN:
                reasons.append(f"**Sortino Ratio ({sortino:.2f})** below minimum ({SORTINO_MIN})")
                
            if not reasons:
                reasons.append("Met all constraints (Might have failed LLM Phase 2 or Sentiment Filter).")
                
            analysis_results.append({"symbol": sym, "reasons": reasons})
            
        except Exception as e:
            analysis_results.append({"symbol": sym, "reasons": [f"Failed to fetch data: {e}"]})
            
    return analysis_results

def format_scanner_cell(sym, scanner_map):
    if sym in scanner_map:
        info = scanner_map[sym]
        return f"✅ Yes ({info['tier']} - {info['grade']})"
    return "❌ No"

def build_markdown(date_str, av_data, gappers, scanner_map, missed_analysis):
    lines = [
        f"# Daily Market Report: {date_str}",
        "",
        "This report is generated automatically by sweeping the market using the AlphaVantage API and cross-referencing with your Cobalt Multiagent scanner hits.",
        ""
    ]
    
    # 1. Top Gainers
    lines.extend(["## Top 10 Market Gainers", ""])
    lines.extend(["| Symbol | Price | Change % | Volume | On Scanner? |", "| :--- | :--- | :--- | :--- | :--- |"])
    for item in av_data.get("top_gainers", [])[:10]:
        sym = item.get("ticker", "")
        price = item.get("price", "0")
        change = item.get("change_percentage", "0")
        vol = item.get("volume", "0")
        on_scan = format_scanner_cell(sym, scanner_map)
        lines.append(f"| {sym} | ${price} | {change} | {vol} | {on_scan} |")
    lines.append("")
    
    # 2. Top Losers
    lines.extend(["## Top 10 Market Losers", ""])
    lines.extend(["| Symbol | Price | Change % | Volume | On Scanner? |", "| :--- | :--- | :--- | :--- | :--- |"])
    for item in av_data.get("top_losers", [])[:10]:
        sym = item.get("ticker", "")
        price = item.get("price", "0")
        change = item.get("change_percentage", "0")
        vol = item.get("volume", "0")
        on_scan = format_scanner_cell(sym, scanner_map)
        lines.append(f"| {sym} | ${price} | {change} | {vol} | {on_scan} |")
    lines.append("")
    
    # 3. Most Actively Traded
    lines.extend(["## Top 10 Most Actively Traded (Volume)", ""])
    lines.extend(["| Symbol | Price | Change % | Volume | On Scanner? |", "| :--- | :--- | :--- | :--- | :--- |"])
    for item in av_data.get("most_actively_traded", [])[:10]:
        sym = item.get("ticker", "")
        price = item.get("price", "0")
        change = item.get("change_percentage", "0")
        vol = item.get("volume", "0")
        on_scan = format_scanner_cell(sym, scanner_map)
        lines.append(f"| {sym} | ${price} | {change} | {vol} | {on_scan} |")
    lines.append("")
    
    # 4. Top Gappers
    lines.extend(["## Top 10 Gappers", "*(Calculated from the open vs previous close of the top gainers/actives)*", ""])
    lines.extend(["| Symbol | Pre-Market Gap % | On Scanner? |", "| :--- | :--- | :--- |"])
    for item in gappers[:10]:
        sym = item["symbol"]
        gap = item["gap_pct"]
        on_scan = format_scanner_cell(sym, scanner_map)
        lines.append(f"| {sym} | {gap:.2f}% | {on_scan} |")
    lines.append("")
    
    # 5. Missed Gainers Analysis
    if missed_analysis:
        lines.extend([
            "## Scanner Miss Analysis", 
            "*(Why did the scanner reject these top gainers?)*",
            ""
        ])
        for miss in missed_analysis:
            sym = miss["symbol"]
            lines.append(f"### {sym}")
            for r in miss["reasons"]:
                lines.append(f"- {r}")
            lines.append("")
            
    return "\n".join(lines)

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    eastern = ZoneInfo("America/New_York")
    date_str = datetime.now(eastern).strftime("%Y-%m-%d")
    
    print(f"Generating Daily Market Report for {date_str}...")
    
    av_data = fetch_av_data()
    if not av_data:
        print("Failed to fetch AlphaVantage data. Exiting.")
        sys.exit(1)
        
    scanner_map = load_scanner_list(date_str, base_dir)
    
    # Identify Missed Gainers
    top_gainers = av_data.get("top_gainers", [])[:10]
    missed_gainers = []
    for g in top_gainers:
        sym = g.get("ticker", "")
        if sym and sym not in scanner_map:
            missed_gainers.append(sym)
            
    # Pool tickers to calculate gaps
    gapper_pool = set()
    for item in av_data.get("top_gainers", [])[:20]: gapper_pool.add(item.get("ticker"))
    for item in av_data.get("most_actively_traded", [])[:20]: gapper_pool.add(item.get("ticker"))
    gapper_pool = list(filter(None, list(gapper_pool)))
    
    print(f"Calculating gaps for {len(gapper_pool)} tickers...")
    gappers = calculate_gappers(gapper_pool)
    
    # Run analysis on missed gainers
    missed_analysis = analyze_missed_gainers(missed_gainers)
    
    md_content = build_markdown(date_str, av_data, gappers, scanner_map, missed_analysis)
    
    out_dir = os.path.join(base_dir, "data", "archive", "daily_market_reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"report_{date_str}.md")
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print(f"Report successfully saved to {out_path}")

if __name__ == "__main__":
    main()

