# Cobalt Workspace DSV Visualization Specification

**Document Version**: 1.0.0  
**Target Platform**: Cobalt Multiagent / VLI Dashboard (`backend/public/vli_dashboard.html`)  
**Strategy Alignment**: Dual-Session Vector (DSV) Strategy  
**Location**: `specs/cobalt_workspace_dsv_visualization_spec.md`

---

## 1. Executive Summary & Objective

This specification details how the **Cobalt Platform Workspace & VLI Dashboard** can be enhanced to visualize **Dual-Session Vector (DSV)** indicators, live session states, SMT correlation matrices, and automated discipline watchdogs. 

By integrating DSV signals directly into the Cobalt UI, the trader gains real-time session awareness, automated execution guardrails, and immediate visibility into high-probability Po3 setups across all 5 copy-traded accounts.

---

## 2. Workspace UI & Layout Enhancements

```
+-----------------------------------------------------------------------------------+
|                            COBALT VLI DASHBOARD - DSV ENGINE                      |
+-----------------------------------------------------------------------------------+
| [HEADER BAR]                                                                      |
|  SESSION: 🟢 NY Silver Bullet (09:45 EST)  |  ASIA RANGE: AH 21450.5 / AL 21380.0    |
|  COPIER: 5 ACCOUNTS ACTIVE                 |  DAILY P&L: -$50.00 / -$150.00 (1/3) |
+---------------------------------------------------+-------------------------------+
|                                                   |                               |
|               LIVE CHART OVERLAY                  |     SMT CORRELATION AUDIT     |
|   - Asian Range Bounds (AH / AL / 50% EQ)         |  +------+-------+------+------+ |
|   - Midnight Open (00:00 EST) Baseline            |  | TICKER | SMT   | FVG  | MSS  | |
|   - 5m MSS / FVG Highlight Boxes                  |  +------+-------+------+------+ |
|   - Order Entry Target Line ($100) / SL ($50)     |  | NQ1! | BULL  | YES  | CONF | |
|                                                   |  | ES1! | BEAR  | NO   | WAIT | |
|                                                   |  | RTY! | FLAT  | YES  | CONF | |
|                                                   |  +------+-------+------+------+ |
+---------------------------------------------------+-------------------------------+
| [DISCIPLINE WATCHDOG BANNER]                                                     |
|  TRADES TAKEN THIS SESSION: 1 / 2  |  LONG DIRECTION: 🔒 LOCKED FOR SESSION       |
|  CIRCUIT BREAKER STATUS: 🟢 OK     |  REMAINING RISK CAP: $100.00                 |
+-----------------------------------------------------------------------------------+
```

---

## 3. Core Component Modules

### Module A: DSV Session & Benchmark Header Widget
* **Session Phase Indicator**: Displays active market window:
  * 🌏 `ASIA ACCUMULATION (18:00 - 02:00 EST)`
  * 🏛️ `LONDON JUDAS SWEEP (02:00 - 08:00 EST)`
  * 🎯 `NY SILVER BULLET EXPANSION (09:45 - 11:30 EST)`
* **Asian Benchmark Metrics**: Displays live values for $AH$, $AL$, $50\%\text{ EQ}$, and Midnight Open.
* **Risk & Account Status**: Shows aggregate exposure across 5 copy-traded accounts.

### Module B: Real-Time SMT Correlation Matrix
* **Inter-Market Divergence Audit**: Continuously compares high/low price wicks between **NQ** (Nasdaq), **ES** (S&P 500), and **M2K** (Russell 2000).
* **Divergence Warning**: Highlights bullish or bearish SMT divergence in real time:
  * 🟩 `NQ lower low + ES higher low = BULLISH SMT SWEEP`
  * 🟥 `NQ higher high + ES lower high = BEARISH SMT SWEEP`

### Module C: Automated Discipline Watchdog (The 3 Circuit Breakers)
* **Session Execution Tracker**: Counts trades executed during the active session (Cap: 2 trades).
* **Directional Lock Banner**: If a Long trade is stopped out, the UI locks the Long button and highlights: `LONG DIRECTION LOCKED FOR THIS SESSION`.
* **Daily Drawdown Meter**: Color-coded progress bar tracking daily cumulative P&L against the -$150.00 limit.

### Module D: TradeZella Auto-Export & Journal Widget
* Automatically formats and downloads session trade logs into TradeZella-ready CSV exports.
* Pre-populates session tags (`#DSV`, `#AsiaFade`, `#NYJudas`, `#SMT_Divergence`) for instant journaling.

---

## 4. Implementation Roadmap for Cobalt Platform

1. **Backend Integration (`backend/src/services/`)**:
   * Build `dsv_session_service.py` to calculate session highs/lows and track Midnight Open.
   * Build `smt_correlation_service.py` to poll correlated futures feeds and trigger SMT alerts via WebSockets.
2. **Frontend Integration (`backend/public/vli_dashboard.html`)**:
   * Add DSV Session Header Widget and Discipline Watchdog Banner.
   * Add SMT Divergence Matrix table to the side panel.
