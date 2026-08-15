import os
import json
import glob
import argparse
from datetime import datetime

SNAPSHOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "strategies", "DSV", "snapshots"))

def list_snapshots():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    files = glob.glob(os.path.join(SNAPSHOT_DIR, "*.json"))
    if not files:
        print("No strategy snapshots found in strategies/DSV/snapshots/")
        return
        
    print("\n==================================================================================")
    print("                    STRATEGY CONFIGURATION SNAPSHOTS REGISTRY")
    print("==================================================================================")
    for fpath in sorted(files):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("metadata", {})
            risk = data.get("capital_and_risk_settings", {})
            symbols = ", ".join(data.get("symbols", []))
            
            print(f"📷 Snapshot ID : {data.get('snapshot_id', 'N/A')}")
            print(f"   File        : {os.path.basename(fpath)}")
            print(f"   Created At  : {data.get('created_at', 'N/A')}")
            print(f"   Symbols     : {symbols}")
            print(f"   Version Tag : {meta.get('version_tag', 'N/A')}")
            print(f"   Capital     : ${risk.get('initial_capital_usd', 0):,.2f} | 1R Risk: ${risk.get('fixed_risk_usd', 0):,.2f} | Daily Cap: {risk.get('max_daily_loss_r', 0)}R")
            if "benchmark_metrics" in meta:
                bm = meta["benchmark_metrics"]
                print(f"   Performance : Net PnL: ${bm.get('net_pnl_usd', 0):,.2f} | WR: {bm.get('win_rate_pct', 0)}% | Payoff: {bm.get('payoff_ratio', 0)} R:R")
            print("-" * 82)
        except Exception as e:
            print(f"Error reading {fpath}: {e}")

def create_snapshot(snapshot_id, symbols, description, version_tag, risk_usd=1000.0, daily_max_r=3.0):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    now_str = datetime.now().isoformat()
    symbol_list = [s.strip() for s in symbols.split(",")]
    
    snapshot_filename = f"{snapshot_id.lower().replace(' ', '_')}.json"
    target_path = os.path.join(SNAPSHOT_DIR, snapshot_filename)
    
    snapshot_data = {
        "schema_version": "1.0.0",
        "snapshot_id": snapshot_id,
        "created_at": now_str,
        "symbols": symbol_list,
        "metadata": {
            "strategy_name": "Dual-Session Vector (DSV) Strategy - DAG Engine",
            "strategy_file": "strategies/DSV/dsv_strategy_dag.pine",
            "version_tag": version_tag,
            "author": "Cobalt Multiagent AI / Pair Programming Team",
            "description": description,
            "notes": "Snapshot captured after tuning strategy parameters.",
            "benchmark_metrics": {}
        },
        "capital_and_risk_settings": {
            "initial_capital_usd": 250000.0,
            "fixed_risk_usd": risk_usd,
            "max_daily_loss_r": daily_max_r,
            "max_daily_loss_usd": risk_usd * daily_max_r,
            "enable_scale_in": True,
            "scale_in_rr_target": 3.0,
            "use_atr_sizing": True,
            "max_sl_ticks": 150
        },
        "time_and_session_settings": {
            "use_asia": True,
            "asia_window_est": "18:00 - 23:00 EST",
            "use_london": True,
            "london_window_est": "02:00 - 08:00 EST",
            "use_ny": True,
            "ny_window_est": "09:30 - 11:15 EST",
            "news_filter": True,
            "block_macro_window": True,
            "macro_window_est": "09:50 - 10:10 EST",
            "pre_ny_blackout_est": "07:00 EST",
            "asia_end_blackout_est": "01:00 EST",
            "use_date_filter": True,
            "horizon_days": 90
        },
        "macro_trend_settings": {
            "htf_timeframe": "1H",
            "ema_fast_period": 50,
            "ema_slow_period": 200,
            "strict_macro_gate": "Price >= 1H 200 EMA & 1H 50 EMA >= 1H 200 EMA (Bullish) | Price <= 1H 200 EMA & 1H 50 EMA < 1H 200 EMA (Bearish)"
        },
        "dag_engine_settings": {
            "sweep_timeframe": "15m",
            "mss_timeframe": "5m",
            "entry_timeframe": "1m",
            "sweep_rvol_min": 1.5,
            "asia_rvol_min": 1.2,
            "rvol_threshold": 1.8,
            "max_mss_bars": 10
        },
        "trailing_stop_settings": {
            "enable_fvg_trail": True,
            "trail_timeframe": "5m",
            "ema21_confirmation_gate": True,
            "stage1_breakeven_lock": "+0.1R at +1.0R Floating Expansion",
            "stage2_structural_lock": "+0.75R at +1.5R Floating Expansion",
            "stage3_fvg_trailing": "21 EMA-Gated 5m FVG Base Trailing"
        }
    }
    
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(snapshot_data, f, indent=2)
        
    print(f"✅ Successfully created snapshot: {target_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DSV Strategy Configuration Snapshots Manager")
    parser.add_argument("--list", action="store_true", help="List all strategy snapshots")
    args = parser.parse_args()
    
    if args.list:
        list_snapshots()
    else:
        list_snapshots()
