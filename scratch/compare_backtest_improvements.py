import os
import sys
import yfinance as yf
from collections import defaultdict

sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from src.server.routes.scanner import run_weekly_5m_replay_backtest
from src.tools.macros import extract_single_ticker_df

test_symbols = [
    "ANAB", "HBM", "TER", "MTW", "TECK", "LPTH", "UNH", "INDV", "RVTY", "BRUN", "NBIS", "AGPU", "INTC", "CIFR",
    "/MGC", "/M2K", "/MYM", "/MCL", "/MNK"
]

print("=== Running Replay Backtest Evaluation (Option A: Buy on Strength + RVOL >= 1.25) ===")

results = []
total_trades = 0
total_wins = 0
total_fails = 0
total_pnl = 0.0
total_rejections = 0
rejections_by_step = defaultdict(int)

for sym in test_symbols:
    norm_sym = sym
    if sym.startswith('/'):
        mapping = {
            '/ES': 'ES=F', '/MES': 'MES=F', '/NQ': 'NQ=F', '/MNQ': 'MNQ=F',
            '/YM': 'YM=F', '/MYM': 'MYM=F', '/RTY': 'RTY=F', '/M2K': 'M2K=F',
            '/CL': 'CL=F', '/MCL': 'MCL=F', '/GC': 'GC=F', '/MGC': 'MGC=F',
            '/NKD': 'NKD=F', '/MNK': 'MNK=F'
        }
        norm_sym = mapping.get(sym, sym.replace('/', '') + '=F')
        
    try:
        df_5m = yf.download(norm_sym, period="1mo", interval="5m", progress=False)
        df_1h = yf.download(norm_sym, period="3mo", interval="1h", progress=False)
        df_1d = yf.download(norm_sym, period="2y", interval="1d", progress=False)
        
        df_5m = extract_single_ticker_df(df_5m, norm_sym)
        df_1h = extract_single_ticker_df(df_1h, norm_sym)
        df_1d = extract_single_ticker_df(df_1d, norm_sym)
        
        is_future = sym.startswith('/') or '=F' in norm_sym
        res = run_weekly_5m_replay_backtest(df_5m, df_1h, df_1d, sym, is_future=is_future)
        
        wins = res["success"]
        fails = res["fail"]
        ledger = res["ledger"]
        rejected = res["rejected_trades"]
        
        for r in rejected:
            rejections_by_step[r.get("step", "Other")] += 1
            
        sym_pnl = sum(t.get("pnl", 0.0) for t in ledger)
        win_rate = (wins / (wins + fails) * 100.0) if (wins + fails) > 0 else 0.0
        
        total_wins += wins
        total_fails += fails
        total_trades += len(ledger)
        total_pnl += sym_pnl
        total_rejections += len(rejected)
        
        results.append({
            "symbol": sym,
            "wins": wins,
            "fails": fails,
            "win_rate": win_rate,
            "pnl": sym_pnl,
            "trades": len(ledger),
            "rejections": len(rejected)
        })
        print(f"Symbol {sym:<6s} | Wins: {wins:<2d} | Fails: {fails:<2d} | WinRate: {win_rate:>5.1f}% | PnL: ${sym_pnl:>8.2f} | Rejections: {len(rejected):<3d}")
    except Exception as e:
        print(f"Error evaluating {sym}: {e}")

overall_win_rate = (total_wins / (total_wins + total_fails) * 100.0) if (total_wins + total_fails) > 0 else 0.0

print("\n" + "="*70)
print(f"SUMMARY PERFORMANCE (Option A: Buy on Strength + RVOL >= 1.25)")
print("="*70)
print(f"Total Symbols Evaluated: {len(results)}")
print(f"Total Executed Trades:   {total_trades} (Wins: {total_wins}, Fails: {total_fails})")
print(f"Overall Win Rate:        {overall_win_rate:.1f}%")
print(f"Total Realized PnL:      ${total_pnl:,.2f}")
print(f"Total Rejected Entries:  {total_rejections}")
print("\nRejection Breakdown by Step:")
for step, count in sorted(rejections_by_step.items(), key=lambda x: x[1], reverse=True):
    print(f"  - {step:<25s}: {count} trades rejected")
print("="*70)
