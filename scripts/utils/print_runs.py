import os
import glob
import json
import sys
from pathlib import Path

# Add script directory to sys.path for reliable imports
sys.path.append(str(Path(__file__).resolve().parent))
from strategy_tracker import process_dropzone

HISTORY_FILE = Path("data/strategy_execution_history.json")

def print_execution_history():
    # 1. Automatically process and archive any pending files in dropzone first!
    process_dropzone()

    if not HISTORY_FILE.exists():
        print(f"❌ Error: {HISTORY_FILE} not found.")
        return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_series = data.get("test_series", {})
    if not test_series:
        print("ℹ️ No test series found in execution history.")
        return

    print("================================================================================")
    print("               STRATEGY EXECUTION HISTORY & PEAK PnL BENCHMARK                 ")
    print("================================================================================")

    for series_name, runs in test_series.items():
        print(f"\n📊 Series: {series_name}")
        print("=" * 80)
        for r in runs:
            m = r.get("metrics", {})
            cfg = r.get("test_config", {})
            tracker = r.get("series_pnl_tracker", {})
            
            run_num = r.get("run_number")
            filename = r.get("filename")
            pnl = m.get("net_pnl_usd", 0.0)
            win_rate = m.get("win_rate_pct", 0.0)
            payoff = m.get("payoff_ratio", 0.0)
            avg_win = m.get("avg_win_usd", 0.0)
            avg_loss = m.get("avg_loss_usd", 0.0)
            worst_hr = m.get("worst_hour", "N/A")
            is_peak = tracker.get("is_at_peak_profit", False)
            peak_badge = " 🏆 (PEAK PROFIT)" if is_peak else ""

            print(f"Run #{run_num:<2} | File: {filename}{peak_badge}")
            print(f"   📅 Window      : {cfg.get('start_date')} ➔ {cfg.get('end_date')}")
            print(f"   💰 Net PnL     : ${pnl:,.2f} | Win Rate: {win_rate}% | Payoff R:R: {payoff}")
            print(f"   ⚖️ Avg Win/Loss : ${avg_win:,.2f} / ${avg_loss:,.2f} | Worst Hour: {worst_hr}")
            print(f"   📈 Series Peak  : ${tracker.get('max_pnl_usd', 0.0):,.2f} | Drawdown from Peak: {tracker.get('drawdown_from_peak_pct', 0.0)}%")
            print("-" * 80)

if __name__ == "__main__":
    print_execution_history()
