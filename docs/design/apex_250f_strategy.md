# Apex 250F Strategy Specification
### *Futures-Dedicated Adaptation of the Apex 500 Strategy ($50,000 Margin Account)*

---

## 1. Executive Summary & Strategy Identity
The **Apex 250F Strategy** is a precision trading framework built around **Smart Money Concepts (SMC)**, designed exclusively for **CME Futures** (`MNQ`/`NQ`, `MES`/`ES`, `MCL`/`CL`, `MGC`/`GC`, `MYM`/`YM`, `M2K`/`RTY`). 

Apex 250F evaluates and adapts all **Apex 500 rules** specifically for a **$50,000 margin account** with standard day-trading futures leverage.

---

## 2. Capital Allocation & Risk Parameters

| Parameter | APEX 500 Rule (Equities) | APEX 250F Rule (Futures) | $50,000 Account Evaluation & Sizing |
| :--- | :--- | :--- | :--- |
| **Account Equity** | $100k+ Portfolio | **$50,000 Margin Account** | Base equity for day-trading futures with standard margin. |
| **Daily Profit Target** | $750 (Floor: $500) | **$750 (Floor: $500)** | **Fits Perfectly**. Represents a +1.5% daily return (+1.0% floor). Achievable via 15–20 pts in `MNQ` or 6–8 pts in `MES`. |
| **Target R:R Ratio** | 1.5:1 – 2.0:1 | **2:1 Minimum R:R** | **Updated**. Minimum 2:1 Reward-to-Risk ratio on all entries ($500 profit target per $250 Strike risk; $250 profit target per $125 Scout risk). |
| **Risk Unit (1.0R)** | $250 (Strike) | **$250 (Strike Size)** | **Fits Perfectly**. Exactly 0.5% risk per trade. Executed via 5 `MNQ` (10-pt stop) or 10 `MES` (5-pt stop) or 1 `NQ`/`ES` contract (tight stop). |
| **Scout Risk Unit (0.5R)**| $125 (Scout) | **$125 (Scout Size)** | **Fits Perfectly**. 0.25% risk per trade. Used for initial probes via 2-3 `MNQ` or 5 `MES` contracts. |
| **Max Daily Loss (DSL)** | ($750) [3.0R] | **($1,000) [4.0R] Hard Stop** | **Updated**. 2.0% max daily drawdown limit ($1,000 max loss). Full system hard-kill if daily PnL reaches ($1,000). |
| **Recovery Gate** | ($500) Drawdown | **($750) Drawdown** | **Updated**. If daily PnL hits ($750), all remaining trades are forced to Scout size ($125 max risk). |

---

## 3. Instrument Selection & Margin Guardrails

| Rule | APEX 500 Rule | APEX 250F Rule | Margin & Leverage Description |
| :--- | :--- | :--- | :--- |
| **Target Universe** | $10–$100 Liquid Equities | **CME Futures Universe Only** | Replaced equity stocks with high-liquidity futures contracts: <br>• **Equity Indices**: `MNQ`/`NQ`, `MES`/`ES`, `MYM`/`YM`, `M2K`/`RTY`<br>• **Commodities**: `MCL`/`CL` (Crude Oil), `MGC`/`GC` (Gold) |
| **Margin Ceiling** | Portfolio Margin | **Max $15,000 Used Margin** | **Margin Overhead Guard**: Total active initial margin across open positions cannot exceed 30% of account equity ($15,000 max), preventing over-leveraging. |

---

## 4. Volume Acceleration & Intraday Liquidity

| Rule | APEX 500 Rule | APEX 250F Rule | Intraday Implementation |
| :--- | :--- | :--- | :--- |
| **RVOL Requirement** | Daily RVOL > 2.0 (10-day lookback) | **Session-Relative RVOL > 1.5–2.0** | Volume is evaluated relative to the **exact 15m session bucket** (e.g., NY Open volume vs. historical 9:30 AM ET volume). Requires 3 consecutive 5m volume acceleration candles prior to entry. |


---

## 5. Technical SMC Structure & CRT Directional Rules

| Rule | APEX 500 Rule | APEX 250F Rule | Futures Market Structure Implementation |
| :--- | :--- | :--- | :--- |
| **Zonal Discipline** | Premium/Discount Fib | **Mandatory Discount Zone Buy** | **Strict Zonal Guard**: Always buy exclusively in the **Discount Zone** (<0.50 / <0.25 Fib). Short entries executed exclusively in the **Premium Zone** (>0.50 / >0.75 Fib). |
| **CRT Breakout & Reversal**| Standard SMC Sweeps | **CRT 15m & 1h Identification** | **CRT Segment Anchoring**: Uses **15m and 1h Candle Range Theory (CRT)** segments to identify structural **Breakouts** (Expansion / BoS) and **Reversals** (Liquidity Sweeps / CHoCH). |
| **Liquidity Sweep** | Previous Day High/Low (PDH/PDL) | **Session Liquidity Sweep** | Must sweep key intraday pools: **Asia High/Low**, **London High/Low**, **NY AM High/Low**, or **Overnight High/Low**. |
| **Market Structure** | 15m Sweep $\rightarrow$ 5m CHoCH | **15m Sweep $\rightarrow$ 5m CHoCH** | **Fits Perfectly**. 5m Change of Character following a 15m/1h CRT Liquidity Sweep, confirmed with Fair Value Gap (FVG) displacement. |
| **POI Entry** | Extreme OB or 50% FVG | **Limit-Trap at Extreme OB / FVG** | **Fits Perfectly**. Limit orders placed at the 5m Order Block or 50% FVG (Consequent Encroachment) within Discount/Premium zones. **No Market Orders allowed.** |

---

## 6. Position Management & Intra-Session Rules

| Rule | APEX 500 Rule | APEX 250F Rule | Futures Risk & Time Management |
| :--- | :--- | :--- | :--- |
| **Trailing Stop** | 2.0x 15m ATR | **2.0x 15m Contract ATR** | **Fits Perfectly**. Automatically trails at 2.0x 15m ATR below/above price. Activates when PnL reaches **+$375** (+1.5R). |
| **Hold Duration** | 1–4 Hours | **1–4 Hours (Mandatory EOD Flat)** | Must review at 60 mins if stagnant. **Mandatory flat before 4:45 PM ET** (or prior to Asian session close). |
| **Correlation Ceiling**| Max 2 positions per sector | **Max 2 Positions / No Index Duplication** | Maximum 2 active positions overall. **Prohibits concurrent positions in correlated index contracts** (e.g., cannot hold long `MNQ` and long `MES` at the same time). |

---

## 7. Macro Compass & Session Execution Windows

| Rule | APEX 500 Rule | APEX 250F Rule | Macro & Session Filter |
| :--- | :--- | :--- | :--- |
| **Macro Regime** | VIX < 23 (Aggressive) / VIX > 25 (Defensive) | **VIX & Session Filter** | • **VIX < 20**: Full Strike Size ($250 R)<br>• **VIX 20–25**: Scout Size Only ($125 R)<br>• **VIX > 25**: Trading Halted / Defensive Standby |
| **US Session Windows** | Regular Trading Hours (9:30 AM ET) | **Structured US Execution Windows** | • **Start Trading**: **9:45 AM ET** (allows 9:30 AM open volatility to settle).<br>• **Lunch Standdown**: **12:00 PM – 1:30 PM ET** (no new entries).<br>• **PM Resume Window**: **1:30 PM – 2:45 PM ET**.<br>• **Exit Preparation**: **2:45 PM ET** (begin closing positions / tight trailing stop). |
| **Asian Session Window**| Excluded (RTH Equities Only) | **Asian Evening Execution Window** | • **Window**: **8:00 PM – 11:00 PM ET**.<br>• Enables high-probability SMC setups around Tokyo/Sydney liquidity sweeps and early Asian trend development. |
