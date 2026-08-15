# 📜 DSV Strategy Optimization & Evolution Log: COMEX_MINI:MGC1! (Gold Futures)

**Symbol**: `COMEX_MINI:MGC1!` (Gold Futures)  
**Timeframe**: 1m Native / 5m MSS / 15m Benchmark / 1h Macro  
**Horizon**: 2026-01-05 to 2026-08-13 (2026 YTD Backtest Horizon)  
**Primary Strategy Engine**: `strategies/DSV/dsv_strategy_dag.pine` (Sequential DAG State Machine)  

---

## 🏆 Current Production Benchmark Summary

| Parameter | Value |
| :--- | :--- |
| **Current Peak Run** | **Run #23** (`ad8e3.csv`) 🏆 |
| **Account Model** | **$250,000 Initial Capital** |
| **Baseline Risk per Trade (1R)** | **$500.00** |
| **Daily Max Loss Limit** | **3.0R ($1,500.00)** |
| **YTD Net PnL** | **+$8,128.00** 🚀 |
| **Win Rate %** | **48.94%** 🟢 |
| **Payoff Ratio (R:R)** | **2.27 R:R** 🚀 |
| **Average Win** | **$653.91** |
| **Average Loss** | **-$288.00** |
| **Total Executions** | **47 Trades** (~1.5 trades/week) |

---

## 📊 Complete Historical Progression Matrix

Below is the complete, chronological record of all optimization runs for `MGC1!`, normalized to both raw testing values and the current scaled **$500 1R Risk Baseline**:

| Run # | Export File | Strategy Logic & Structural Changes | Raw PnL ($) | Scaled PnL ($500 1R) | Win Rate % | Payoff R:R | Trades | Benchmark Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Run #1** | `15_56426.csv` | Initial DAG State Machine baseline | `$-707.00` | `$-1,414.00` | 25.00% | 0.28 | 8 | 🔴 Regression |
| **Run #2** | `15_b9309.csv` | Initial DAG State Machine baseline | `$-707.00` | `$-1,414.00` | 25.00% | 0.28 | 8 | 🔴 Regression |
| **Run #3** | `15_6bb1d.csv` | Refined 1m FVG entry rules | `$25.00` | `$50.00` | 16.67% | 2.23 | 6 | 🟢 Positive |
| **Run #4** | `15_eae32.csv` | Historical window testing | `$-31.00` | `$-62.00` | 0.00% | 0.00 | 2 | 🔴 Regression |
| **Run #5** | `15_072f8.csv` | Historical window testing | `$0.00` | `$0.00` | 0.00% | 0.00 | 1 | 🟢 Positive |
| **Run #6** | `15_19539.csv` | Historical window testing | `$-38.00` | `$-76.00` | 0.00% | 0.00 | 2 | 🔴 Regression |
| **Run #7** | `15_94b11.csv` | 2025-2026 Peak Engine baseline ($762 PnL) | `$738.00` | `$1,476.00` | 29.41% | 8.68 | 17 | 🟢 Positive |
| **Run #8** | `15_d3379.csv` | 2025-2026 Peak Engine baseline ($762 PnL) | `$762.00` | `$1,524.00` | 50.00% | 3.95 | 10 | 🏆 PEAK BENCHMARK |
| **Run #9** | `15_212d0.csv` | YTD 2026 baseline restoration ($440 PnL) | `$440.00` | `$880.00` | 28.57% | 4.79 | 14 | 🟢 Positive |
| **Run #10** | `15_c44b8.csv` | YTD 2026 baseline restoration ($440 PnL) | `$165.00` | `$330.00` | 26.67% | 3.69 | 15 | 🟢 Positive |
| **Run #11** | `15_9e177.csv` | YTD 2026 baseline restoration ($440 PnL) | `$-276.00` | `$-552.00` | 22.22% | 1.30 | 9 | 🔴 Regression |
| **Run #12** | `ored_440.csv` | YTD 2026 baseline restoration ($440 PnL) | `$440.00` | `$880.00` | 28.57% | 4.79 | 14 | 🟢 Positive |
| **Run #13** | `15_b7cef.csv` | Raw 5m FVG Base trailing stop test (no partial exits) | `$-7,530.00` | `$-15,060.00` | 33.93% | 1.39 | 224 | 🔴 Regression |
| **Run #14** | `15_58cb2.csv` | 21 EMA 5m FVG Trailing Stop engine introduction | `$-1,972.00` | `$-3,944.00` | 31.85% | 1.79 | 135 | 🔴 Regression |
| **Run #15** | `15_276b4.csv` | +0.1R Breakeven lock at +1.0R floating expansion | `$-1,989.00` | `$-3,978.00` | 37.72% | 1.33 | 114 | 🔴 Regression |
| **Run #16** | `15_991dc.csv` | Strict Node 0 Master Operational Gate (`execution_permitted`) | `$540.00` | `$1,080.00` | 40.26% | 1.61 | 77 | 🟢 Positive |
| **Run #17** | `15_f39fb.csv` | Strict 1H Macro Trend Alignment Filter (`strict_macro_bullish`) | `$2,455.00` | `$4,910.00` | 44.07% | 1.98 | 59 | 🏆 PEAK BENCHMARK |
| **Run #18** | `15_1fa83.csv` | Asian Session Window Compression (18:00 - 23:00 EST) | `$2,738.00` | `$5,476.00` | 44.90% | 2.10 | 49 | 🏆 PEAK BENCHMARK |
| **Run #19** | `15_d0fbb.csv` | 1m FVG Stack Scale-In 3.0R Target Expansion | `$2,738.00` | `$5,476.00` | 44.90% | 2.10 | 49 | 🏆 PEAK BENCHMARK |
| **Run #20** | `15_92e79.csv` | Removed 21 EMA gate (Raw 5m FVG trailing test) | `$-330.00` | `$-660.00` | 25.64% | 2.08 | 39 | 🔴 Regression |
| **Run #21** | `15_d91d5.csv` | Re-activated 21 EMA gate + Proposal D milestone locks | `$2,745.00` | `$5,490.00` | 45.83% | 2.09 | 48 | 🏆 PEAK BENCHMARK |
| **Run #22** | `15_86e11.csv` | Scaled to $250k account ($500 1R) + 2R Daily Max Cap | `$8,128.00` | `$8,128.00` | 48.94% | 2.27 | 47 | 🏆 PEAK BENCHMARK |
| **Run #23** | `15_ad8e3.csv` | Expanded Daily Max Loss Cap to 3R ($1,500) | `$8,128.00` | `$8,128.00` | 48.94% | 2.27 | 47 | 🏆 PEAK BENCHMARK |

---

## 🔬 Detailed Phase-by-Phase Technical Analysis

### Phase 1: Baseline DAG Engine & Session Filters (Runs #1 - #12)
* **Goal**: Establish 5-node Directed Acyclic Graph state machine for Gold futures (`MGC1!`).
* **Key Architecture**:
  * Node 0: Idle State / Session Validation
  * Node 1: 15m Session High/Low Liquidity Sweep
  * Node 2: 5m Market Structure Shift (MSS) Displacement with RVOL Filter
  * Node 3: 1m Fair Value Gap (FVG) Retest & 2-Candle Rebalance Confirmation
  * Node 5: Entry Execution
  * Node 6: Position Management

### Phase 2: Full Trend Runner Architecture (Runs #13 - #15)
* **Goal**: Eliminate partial profit-taking (T1 scale-outs) to capture long-tail momentum expansions.
* **Findings**:
  * **Run #13**: Removing T1 exits while using raw 5m FVG trailing caused premature stop-outs during volatility noise (`-$7,530.00 PnL`).
  * **Run #14**: Introduced **21 EMA Confirmation Gate** on 5m FVG updates. Stopped premature exits (`+$5,558.00 recovery`).
  * **Run #15**: Introduced **+0.1R Breakeven Lock at +1.0R Expansion** to eliminate floating profit giveback. Identified -$2,093 07:00 EST pre-market drag.

### Phase 3: Gate Hardening & Macro Trend Alignment (Runs #16 - #19)
* **Goal**: Plug operational blackout leaks and align entries strictly with macro trend direction.
* **Findings**:
  * **Run #16**: Enforced `execution_permitted` at Node 0, blocking blackout sweeps (`+$540.00 Net PnL`).
  * **Run #17**: Enforced **Strict 1H Macro Trend Alignment** (Price $\ge$ 1H 200 EMA & 1H 50 EMA $\ge$ 1H 200 EMA). Eliminated counter-trend short losses, driving PnL to **+$2,455.00**.
  * **Run #18**: Compressed Asian Session Window to **18:00 - 23:00 EST**, eliminating late-night Asian drift (`+$2,738.00 Net PnL`).
  * **Run #19**: Expanded 1m FVG Stack scale-in target to **3.0R**, maintaining peak equity.

### Phase 4: Trailing Engine Stress Test (Runs #20 - #21)
* **Goal**: Test removing the 21 EMA gate in favor of raw 5m FVG trailing.
* **Findings**:
  * **Run #20**: Removing 21 EMA gate caused average win to collapse from $299 to $84 (`-$330 PnL`). Proved 21 EMA gate is mandatory for trend breathing room.
  * **Run #21**: Re-activated 21 EMA gate while retaining Proposal D milestone locks (`+0.1R` at +1.0R, `+0.75R` at +1.5R). PnL reached **+$2,745.00** (45.83% Win Rate).

### Phase 5: Capital Scaling & Circuit Breakers (Runs #22 - #23)
* **Goal**: Scale up to $250,000 account model with $500 1R baseline risk and Daily Max Loss circuit breaker.
* **Findings**:
  * **Run #22**: Implemented $500 1R baseline risk + 2R ($1,000) Daily Max Loss Cap. PnL exploded to **+$8,128.00 Net Profit** (48.94% Win Rate / 2.27 Payoff R:R).
  * **Run #23**: Set Daily Max Loss Cap to 3R ($1,500). Maintained **+$8,128.00 Net Profit** with 100% equity stability.

---

## 📌 Master Production Parameter Configuration

```pine
// Capital & Risk Controls
initial_capital  = 250000.00  // $250,000 Account Size
fixed_risk_usd   = 500.00     // $500 1R Risk Baseline per Trade
max_daily_loss_r = 3.0        // 3R ($1,500) Daily Max Loss Circuit Breaker

// Time Window Controls (America/New_York)
in_asia_window   = (t_hour >= 18 and t_hour <= 22) // 18:00 - 23:00 EST
in_london_window = (t_hour >= 2 and t_hour < 8)    // 02:00 - 08:00 EST
in_ny_window     = (t_hour == 9 and t_min >= 30) or t_hour == 10 or (t_hour == 11 and t_min <= 15)

// Blackout Gates
is_pre_ny_blackout   = (t_hour == 7) // 07:00 EST London Pre-Market Blackout
is_asia_end_blackout = (t_hour == 1) // 01:00 EST Asian End Blackout
is_news_blackout     = news_filter and (t_hour == 8 and t_min >= 15 and t_min <= 40)
is_macro_window      = block_macro_window and (t_hour == 9 and t_min >= 50 or (t_hour == 10 and t_min <= 10))

// Structural Macro Filter
strict_macro_bullish = (htf60_close >= htf60_ema200) and (htf60_ema50 >= htf60_ema200)
strict_macro_bearish = (htf60_close <= htf60_ema200) and (htf60_ema50 < htf60_ema200)
```
