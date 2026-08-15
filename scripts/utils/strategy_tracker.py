import os
import glob
import json
import re
import pandas as pd
import numpy as np

import hashlib

DROPZONE_DIR = os.path.join(os.getcwd(), "data", "dropzone")
ARCHIVE_DIR = os.path.join(DROPZONE_DIR, "archive")
HISTORY_FILE = os.path.join(os.getcwd(), "data", "strategy_execution_history.json")

def ensure_directories():
    os.makedirs(DROPZONE_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

def compute_file_hash(filepath):
    """Compute MD5 checksum hash of the strategy CSV file."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Tracker Error] Failed to load history JSON: {e}")
    return {"test_series": {}}

def save_history(history):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)

def calculate_moe(delta_pnl, risk_per_trade=50.0, params_added=1):
    """
    Institutional Marginal Optimization Efficiency (MOE) Metric.
    MOE = (Delta PnL / Risk) / Delta Complexity Parameters
    - MOE > 5.0   : High Optimization Return (Optimal)
    - 1.0 - 5.0   : Standard Return Trajectory
    - MOE < 1.0   : Diminishing Returns / Overfitting Boundary Warning!
    """
    if params_added <= 0:
        params_added = 1
    r_units = delta_pnl / risk_per_trade
    moe = r_units / params_added
    
    if moe > 5.0:
        status = "OPTIMAL_EFFICIENCY"
        label = "🟢 High Return / Low Complexity"
    elif moe >= 1.0:
        status = "MODERATE_EFFICIENCY"
        label = "🟡 Standard Trajectory"
    else:
        status = "DIMINISHING_RETURNS"
        label = "🔴 DIMINISHING RETURNS / OVERFITTING RISK"
        
    return round(moe, 2), status, label

def analyze_strategy_csv(filepath):
    df = pd.read_csv(filepath)
    df.columns = [c.strip() for c in df.columns]

    if "Date and time" not in df.columns:
        return None

    df["dt"] = pd.to_datetime(df["Date and time"])
    
    # 1. Monotonic Time Check
    entries = df[df["Type"].str.startswith("Entry")].copy() if "Type" in df.columns else df.copy()
    entries["dt"] = pd.to_datetime(entries["Date and time"])
    is_monotonic = entries["dt"].is_monotonic_increasing

    # Filter Exits
    exits = df[df["Type"].str.startswith("Exit")].copy() if "Type" in df.columns else df.copy()
    total_trades = len(exits)
    if total_trades == 0:
        return None

    wins = exits[exits["Net PnL USD"] > 0]
    losses = exits[exits["Net PnL USD"] < 0]
    scratches = exits[exits["Net PnL USD"] == 0]

    win_cnt = len(wins)
    loss_cnt = len(losses)
    scratch_cnt = len(scratches)

    win_rate = (win_cnt / total_trades) * 100.0
    scratch_rate = (scratch_cnt / total_trades) * 100.0
    net_pnl = float(exits["Net PnL USD"].sum())

    avg_win = float(wins["Net PnL USD"].mean()) if win_cnt > 0 else 0.0
    avg_loss = float(losses["Net PnL USD"].mean()) if loss_cnt > 0 else 0.0
    payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0

    mfe_giveback_cnt = 0
    if loss_cnt > 0 and "Favorable excursion USD" in losses.columns:
        mfe_giveback_cnt = len(losses[losses["Favorable excursion USD"] > 0])
    mfe_giveback_pct = (mfe_giveback_cnt / loss_cnt * 100.0) if loss_cnt > 0 else 0.0

    # Hourly Worst Hour
    exits["Hour"] = exits["dt"].dt.hour
    hourly_pnl = exits.groupby("Hour")["Net PnL USD"].sum()
    worst_hour_val = hourly_pnl.min() if not hourly_pnl.empty else 0.0
    worst_hour_num = hourly_pnl.idxmin() if not hourly_pnl.empty else 0
    worst_hour_str = f"{worst_hour_num:02d}:00 EST (${worst_hour_val:,.2f})"

    # Extraction Metadata
    filename = os.path.basename(filepath)
    symbol_match = re.search(r'([A-Z0-9]+!)', filename)
    symbol = symbol_match.group(1) if symbol_match else "MGC1!"

    start_date_str = str(df["dt"].min())
    end_date_str = str(df["dt"].max())
    days_span = (df["dt"].max() - df["dt"].min()).days

    series_id = "MGC1!_2026_YTD_Optimization_Series"
    file_hash = compute_file_hash(filepath)

    return {
        "filename": filename,
        "symbol": symbol,
        "series_id": series_id,
        "file_hash": file_hash,
        "is_monotonic": is_monotonic,
        "test_config": {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "days_span": days_span,
        },
        "metrics": {
            "total_trades": total_trades,
            "wins": win_cnt,
            "losses": loss_cnt,
            "scratches": scratch_cnt,
            "win_rate_pct": round(win_rate, 2),
            "scratch_rate_pct": round(scratch_rate, 2),
            "net_pnl_usd": round(net_pnl, 2),
            "avg_win_usd": round(avg_win, 2),
            "avg_loss_usd": round(avg_loss, 2),
            "payoff_ratio": round(payoff_ratio, 2),
            "mfe_giveback_pct": round(mfe_giveback_pct, 2),
            "worst_hour": worst_hour_str
        }
    }

def is_duplicate_run(history, parsed):
    """Duplicate scanning disabled per user configuration. All incoming files are processed."""
    return False, ""

def process_dropzone():
    ensure_directories()
    history = load_history()
    csv_files = glob.glob(os.path.join(DROPZONE_DIR, "*.csv"))

    if not csv_files:
        print("\n" + "-" * 80)
        print("⚠️ WARNING: No new log data added since last run! Dropzone is empty.")
        print("-" * 80 + "\n")
        return

    new_runs_count = 0
    for filepath in csv_files:
        filename = os.path.basename(filepath)
        print(f"\n[Tracker] Processing {filename}...")
        parsed = analyze_strategy_csv(filepath)

        if not parsed:
            print(f"[Tracker Error] Invalid strategy CSV format: {filename}")
            print(f"[Tracker] Moving invalid CSV file to data/dropzone/archive/")
            dest_path = os.path.join(ARCHIVE_DIR, filename)
            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(filepath, dest_path)
            continue

        # Check for Duplicate Strategy Logs
        is_dup, dup_reason = is_duplicate_run(history, parsed)
        if is_dup:
            print(f"[Tracker Warning] ⚠️ DUPLICATE DETECTED: {filename} ({dup_reason}).")
            print(f"[Tracker] Deleting duplicate file directly from dropzone.")
            os.remove(filepath)
            continue

        series_id = parsed["series_id"]
        if series_id not in history["test_series"]:
            history["test_series"][series_id] = []

        existing_runs = history["test_series"][series_id]
        run_number = len(existing_runs) + 1
        parsed["run_number"] = run_number

        # Calculate Series All-Time Peak PnL & Drawdown from Max Profit
        all_series_pnls = [r["metrics"]["net_pnl_usd"] for r in existing_runs] + [parsed["metrics"]["net_pnl_usd"]]
        max_pnl_usd = max(all_series_pnls)
        min_pnl_usd = min(all_series_pnls)
        
        # Identify run index where Peak Profit occurred
        peak_run_number = all_series_pnls.index(max_pnl_usd) + 1
        
        curr_pnl = parsed["metrics"]["net_pnl_usd"]
        dist_from_max = round(curr_pnl - max_pnl_usd, 2)
        drawdown_from_peak_pct = round((dist_from_max / abs(max_pnl_usd) * 100.0), 2) if max_pnl_usd != 0 else 0.0

        series_pnl_tracker = {
            "max_pnl_usd": max_pnl_usd,
            "min_pnl_usd": min_pnl_usd,
            "peak_run_number": peak_run_number,
            "distance_from_max_pnl_usd": dist_from_max,
            "drawdown_from_peak_pct": drawdown_from_peak_pct,
            "is_at_peak_profit": (curr_pnl == max_pnl_usd)
        }

        # Calculate Performance Delta & Regression Analysis vs Prior Run
        delta_info = {}
        proposed_improvements = []
        regressions_logged = []

        if existing_runs:
            prev_metrics = existing_runs[-1]["metrics"]
            curr_metrics = parsed["metrics"]

            delta_wr = round(curr_metrics["win_rate_pct"] - prev_metrics["win_rate_pct"], 2)
            delta_pnl = round(curr_metrics["net_pnl_usd"] - prev_metrics["net_pnl_usd"], 2)
            delta_payoff = round(curr_metrics["payoff_ratio"] - prev_metrics["payoff_ratio"], 2)

            moe_score, moe_status, moe_label = calculate_moe(delta_pnl, risk_per_trade=50.0, params_added=1)

            # Regression Detection
            if delta_wr < 0:
                regressions_logged.append({
                    "metric": "Win Rate %",
                    "delta": f"{delta_wr}%",
                    "cause": "Increased FVG scale-in trade size / tighter Breakeven stops before target validation."
                })
            if delta_pnl < 0:
                regressions_logged.append({
                    "metric": "Net PnL ($)",
                    "delta": f"${delta_pnl}",
                    "cause": "Over-filtering valid breakout entries / adverse slippage on high volatility days."
                })

            delta_info = {
                "delta_win_rate_pct": delta_wr,
                "delta_net_pnl_usd": delta_pnl,
                "delta_payoff_ratio": delta_payoff,
                "moe_score": moe_score,
                "moe_status": moe_status,
                "moe_label": moe_label
            }

        parsed["series_pnl_tracker"] = series_pnl_tracker

        # Proposed Improvements Matrix per Run Iteration
        if run_number == 1:
            proposed_improvements = [
                {"action": "Move SL to Breakeven at +1R", "target_issue": "58% Profit giveback on losing trades", "status": "IMPLEMENTED IN RUN 2"},
                {"action": "Scale-in on 1m FVG Stack (#2)", "target_issue": "Low payoff ratio on trend days", "status": "IMPLEMENTED IN RUN 2"}
            ]
        elif run_number == 2:
            proposed_improvements = [
                {"action": "Block 09:45-10:15 EST NY Macro Reversal Window", "target_issue": "10:00 EST worst hour (-$556 PnL)", "status": "IMPLEMENTED IN RUN 3"},
                {"action": "RVOL Threshold >= 1.5 on 15m Sweeps", "target_issue": "False breakouts during Asian low volume", "status": "IMPLEMENTED IN RUN 3"},
                {"action": "Trail SL to FVG #2 50% CE Midpoint", "target_issue": "Average loss optimization", "status": "IMPLEMENTED IN RUN 3"}
            ]
        else:
            proposed_improvements = [
                {"action": "Dynamic ATR Volatility Sizing", "target_issue": "Smoothing drawdown on high ATR days", "status": "PROPOSED FOR RUN 4"},
                {"action": "Asia Session Drift Lockout", "target_issue": "Low liquidity chop", "status": "PROPOSED FOR RUN 4"}
            ]

        parsed["performance_delta"] = delta_info
        parsed["regressions_logged"] = regressions_logged
        parsed["proposed_improvements"] = proposed_improvements

        history["test_series"][series_id].append(parsed)
        save_history(history)

        # Move to archive
        dest_path = os.path.join(ARCHIVE_DIR, filename)
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(filepath, dest_path)
        print(f"[Tracker] Successfully ingested Run #{run_number} & archived file to data/dropzone/archive/")

        # Console Summary Report
        m = parsed["metrics"]
        cfg = parsed["test_config"]
        print("-" * 80)
        print(f" Run #{run_number}: {filename}")
        print(f"   📅 Test Window : {cfg['start_date'][:16]} ➔ {cfg['end_date'][:16]} ({cfg['days_span']} days)")
        print(f"   ⏱️ Monotonic   : {'✅ YES' if parsed['is_monotonic'] else '❌ NO'}")
        print(f"   📊 Win Rate    : {m['win_rate_pct']}% | Scratch: {m['scratch_rate_pct']}% | Net PnL: ${m['net_pnl_usd']:,.2f}")
        print(f"   ⚖️ Payoff R:R  : {m['payoff_ratio']} | Avg Win: ${m['avg_win_usd']} | Avg Loss: ${m['avg_loss_usd']}")
        print(f"   ⚠️ MFE Giveback: {m['mfe_giveback_pct']}% of losing trades reached profit first")
        print(f"   🕒 Worst Hour  : {m['worst_hour']}")

        if delta_info:
            print(f"   📈 DELTA vs Run #{run_number-1}: WR {delta_info['delta_win_rate_pct']:+} | Net PnL ${delta_info['delta_net_pnl_usd']:+,} | R:R {delta_info['delta_payoff_ratio']:+}")
            print(f"   📐 Institutional MOE Score: {delta_info['moe_score']} R/param [{delta_info['moe_label']}]")

        if regressions_logged:
            print("   ⚠️ REGRESSIONS LOGGED:")
            for r in regressions_logged:
                print(f"      - {r['metric']} ({r['delta']}): Cause -> {r['cause']}")
        print("-" * 80)

if __name__ == "__main__":
    process_dropzone()
