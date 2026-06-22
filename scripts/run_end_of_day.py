import os
import sys
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def main():
    print("=" * 60)
    print(" VLI End of Day Execution & Export Suite")
    print("=" * 60)
    
    # Resolve project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(project_root)
    
    # Get today and tomorrow dates in Eastern Time
    eastern = ZoneInfo("America/New_York")
    today_dt = datetime.now(eastern)
    today_str = today_dt.strftime("%Y-%m-%d")
    tomorrow_dt = today_dt + timedelta(days=1)
    tomorrow_str = tomorrow_dt.strftime("%Y-%m-%d")
    
    print(f"Current Date (ET): {today_str}")
    
    # 1. Run TradeZella Export for today
    print("\n[1/3] Running TradeZella Exporter (Daily View)...")
    today_output = os.path.join("data", "exports", "tradezella-import-today.csv")
    cmd_today = [
        sys.executable,
        "scripts/export_tradezella.py",
        "--start", today_str,
        "--end", tomorrow_str,
        "--output", today_output
    ]
    try:
        res = subprocess.run(cmd_today, capture_output=True, text=True, check=True)
        print(res.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error executing daily TradeZella export: {e}")
        print(e.stdout)
        print(e.stderr)
        
    # 2. Run TradeZella Export for the whole week
    print("\n[2/3] Running TradeZella Exporter (Weekly View)...")
    weekly_output = os.path.join("data", "exports", "tradezella-import.csv")
    cmd_weekly = [
        sys.executable,
        "scripts/export_tradezella.py",
        "--output", weekly_output
    ]
    try:
        res = subprocess.run(cmd_weekly, capture_output=True, text=True, check=True)
        print(res.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error executing weekly TradeZella export: {e}")
        print(e.stdout)
        print(e.stderr)
        
    # 3. Run TradingView Pine Script Generator
    print("\n[3/3] Generating TradingView Trades Plotter Pine Script...")
    cmd_tv = [
        sys.executable,
        "scripts/utils/generate_tradingview_script.py"
    ]
    try:
        res = subprocess.run(cmd_tv, capture_output=True, text=True, check=True)
        print(res.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error generating TradingView script: {e}")
        print(e.stdout)
        print(e.stderr)
        
    # 4. Generate Daily Market Report
    print("\n[4/4] Generating Daily Market Report (AlphaVantage + Scanner Sweep)...")
    cmd_market = [
        sys.executable,
        "scripts/generate_daily_market_report.py"
    ]
    try:
        res = subprocess.run(cmd_market, capture_output=True, text=True, check=True)
        print(res.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error generating market report: {e}")
        print(e.stdout)
        print(e.stderr)
        
    # Print status report of exports
    print("\n" + "=" * 60)
    print(" End of Day Exports Summary")
    print("=" * 60)
    
    exports = [
        ("Daily TradeZella Import", today_output),
        ("Weekly TradeZella Import", weekly_output),
        ("TradingView Pine Script", os.path.join("data", "exports", "tradingview_trades.pine")),
        ("Daily Market Report", os.path.join("data", "archive", "daily_market_reports", f"report_{today_str}.md"))
    ]
    
    for label, path in exports:
        if os.path.exists(path):
            size = os.path.getsize(path)
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[SUCCESS] {label:<25} | Size: {size:>6} bytes | Updated: {mtime}")
        else:
            print(f"[FAILED]  {label:<25} | File not found at {path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
