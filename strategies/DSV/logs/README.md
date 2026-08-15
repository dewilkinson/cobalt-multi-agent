# 📂 DSV Strategy Symbol Optimization Logs

This directory contains symbol-specific optimization logs and backtest histories for the **Dual-Session Vector (DSV)** strategy engine (`strategies/DSV/dsv_strategy_dag.pine`).

---

## 📜 Active Symbol Logs

| Symbol | Asset Name | Current Peak Run | YTD Net PnL ($500 1R) | Win Rate % | Log File |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `COMEX_MINI:MGC1!` | Gold Futures | **Run #23** (`ad8e3.csv`) | **+$8,128.00** | **48.94%** | [`MGC1_Optimization_Log.md`](./MGC1_Optimization_Log.md) |
| `NYMEX:MCL1!` | Micro Crude Oil | *Pending Benchmarking* | -- | -- | *To be created on first test* |
| `CME_MINI:NQ1!` | E-mini Nasdaq-100 | *Pending Benchmarking* | -- | -- | *To be created on first test* |
| `CME_MINI:ES1!` | E-mini S&P 500 | *Pending Benchmarking* | -- | -- | *To be created on first test* |

---

## 🛠️ Log Generation & Automated Ingestion System

1. **Dropzone Ingestion Daemon**: Runs continuously via `scripts/utils/dropzone_watcher.py`.
2. **Strategy Tracker**: Records every run sequentially into `data/strategy_execution_history.json`.
3. **Symbol Log Compiler**: Generates structured Markdown logs per symbol in `strategies/DSV/logs/[SYMBOL]_Optimization_Log.md`.
