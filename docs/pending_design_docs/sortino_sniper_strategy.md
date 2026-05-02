# APEX 500: Sortino Sniper V2 Implementation Plan

## 1. Core Mandate & Strategy Identity
**Strategy:** Sortino Sniper V2 (Precision Intraday)
**Primary Goal:** Generate a daily profit of **$750** (Minimum **$500** floor).
**Risk Unit (R):** $250 (Strike) | $125 (Scout).
**Daily Stop-Loss (DSL):** **($750)** — (Equates to 3R).
**Hold Duration:** 1–4 Hours.

## 2. The 'Low-Twitch' Execution Policy
To accommodate slower reflex profiles, the system prohibits market chasing. All entries must be executed via 'Limit-Traps'.
- **No Market Orders:** Entries are set as limit orders at pre-defined structural levels.
- **Timeframe Anchor:** 5-Minute (Execution) and 15-Minute (Trend/Structure).
- **Execution Buffer:** 5–15 minute decision windows from alert to execution.

## 3. Selection Criteria (Scout Agent)
The Scout Agent filters the $20–$50 asset universe based on institutional participation:
- **RVOL Acceleration:** Must show increasing volume over three consecutive 5m candles.
- **RVOL Threshold:** Absolute RVOL must be **> 2.0**.
- **Liquidity Sweep:** Mandatory sweep of Previous Session High (PSH) or Previous Session Low (PSL).
- **Sortino Hurdle ($S_{DR}$):** Minimum projected **3.5** (Penalizing downside deviation over total volatility).

## 4. Technical Logic (Smart Money Concepts)
The Analyst Node authorizes trades only when the following confluence exists:
1. **Market Structure:** 5m Change of Character (CHoCH) following a 15m Liquidity Sweep.
2. **Displacement:** Clear Fair Value Gap (FVG) creation on the CHoCH leg.
3. **POI (Point of Interest):** Entry at the **Extreme Order Block (OB)** or 50% FVG (Consequent Encroachment).
4. **Zonal Discipline:** Entry must be in the **Deep Discount/Premium Zone** (<0.25 or >0.75 Fibonacci).

## 5. Risk & Trade Management
- **Risk Escalation:** Start the session with a **Scout ($125)**. Upgrade to **Strike ($250)** only after reaching Break-Even or profit on the initial probe.
- **Trailing Stop:** Automated **2.0x ATR (15m)** trailing stop.
- **Trail Activation:** Activates at **+$375** (+1.5R).
- **Correlation Ceiling:** Maximum of 2 open positions in the same sector.
- **Time Decay:** If a trade is stagnant/red at the 60-minute mark, manual review for exit. Mandatory exit at 4 hours.

## 6. Daily Stop-Loss Protocol
- **Hard Stop:** If Daily Delta hits **($750)**, all DeerFlow nodes terminate immediately.
- **The Recovery Gate:** If drawdown hits ($500), all remaining trades are forced to Scout size ($125) to preserve capital.

## 7. Reporting & Compliance
- **Negative Integer Formatting:** Use ( ) for all negative numbers (e.g., ($250)).
- **Metrics Tracking:** Weekly reporting on Sharpe Efficiency and Sortino Resilience.
- **Rule #1:** Data > Opinion. If the $S_{DR}$ hurdle is not met, the trade does not exist.
