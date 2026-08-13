# Master Guide: Candle Range Theory (CRT) Setup & Execution

---

## 1. Executive Summary & Strategy Identity

**Candle Range Theory (CRT)** is an institutional price-action framework that uses closed higher-timeframe candles (**15-Minute** and **1-Hour**) to define structural dealing ranges. 

Instead of guessing market direction, CRT tracks how institutional liquidity (smart money) sweeps the extremes of a benchmark candle range to trap retail traders before expanding in the true intended direction.

---

## 2. Core CRT Concepts & Range Zoning

A CRT benchmark range is defined as soon as a 15-Minute or 1-Hour candle closes. This candle establishes three critical reference lines:

* **CRT High (Premium Extreme)**: Highest point of the benchmark candle wick.
* **CRT Low (Discount Extreme)**: Lowest point of the benchmark candle wick.
* **CRT Equilibrium (50% Level)**: The exact midpoint between the High and Low.

```
       +-----------------------------------+  <-- CRT High (100%)
       |          PREMIUM ZONE             |
       |  (Exclusively for Short Entries)  |
       +-----------------------------------+  <-- CRT Equilibrium (50%)
       |          DISCOUNT ZONE            |
       |  (Exclusively for Long Entries)   |
       +-----------------------------------+  <-- CRT Low (0%)
```

### **Zonal Execution Rule**
* **Discount Zone (<50% Fib)**: Reserved **exclusively for Long entries**.
* **Premium Zone (>50% Fib)**: Reserved **exclusively for Short entries**.

---

## 3. Directional Entry Conditions (The 4 CRT Setup Types)

### **Setup Type A: Bullish CRT Reversal (Liquidity Sweep)**
Used when institutions sweep sell-side liquidity below the CRT Low before driving price upward.

* **Step 1 (Sweep)**: Price dips below the **15m / 1h CRT Low** to grab sell-stop liquidity.
* **Step 2 (Displacement)**: Price aggressively pushes back inside the CRT range on the 5-minute timeframe.
* **Step 3 (CHoCH)**: A 5m candle breaks structurally upward (**Change of Character**), leaving behind a 5m Fair Value Gap (FVG) or Order Block (OB).
* **Step 4 (Entry)**: Place a **Limit-Trap Buy Order** at the 5m OB or 50% FVG, located inside the **Discount Zone (<50% Fib)**.
* **Stop-Loss**: Placed 2 ticks below the lowest wick of the sweep.
* **Take-Profit**: 15m/1h CRT High (Targeting 2:1 Minimum R:R).

---

### **Setup Type B: Bearish CRT Reversal (Liquidity Sweep)**
Used when institutions sweep buy-side liquidity above the CRT High before driving price downward.

* **Step 1 (Sweep)**: Price spikes above the **15m / 1h CRT High** to grab buy-stop liquidity.
* **Step 2 (Displacement)**: Price aggressively pushes back inside the CRT range on the 5-minute timeframe.
* **Step 3 (CHoCH)**: A 5m candle breaks structurally downward (**Change of Character**), leaving behind a 5m FVG or OB.
* **Step 4 (Entry)**: Place a **Limit-Trap Sell Limit Order** at the 5m OB or 50% FVG, located inside the **Premium Zone (>50% Fib)**.
* **Stop-Loss**: Placed 2 ticks above the highest wick of the sweep.
* **Take-Profit**: 15m/1h CRT Low (Targeting 2:1 Minimum R:R).

---

### **Setup Type C: Bullish CRT Breakout (Expansion / Continuation)**
Used when institutions expand price aggressively out of the CRT dealing range without reversing.

* **Step 1 (Displacement Breakout)**: A 15-minute candle closes body-above the CRT High with strong volume acceleration (RVOL > 1.5).
* **Step 2 (Retest)**: Price pulls back to retest the broken **CRT High** or an open 5m FVG.
* **Step 3 (Entry)**: Enter Long on the retest of the broken CRT High boundary.
* **Stop-Loss**: Placed below the 5m swing low inside the breakout leg.
* **Take-Profit**: Next major liquidity pool (Targeting 2:1 Minimum R:R).

---

### **Setup Type D: Bearish CRT Breakout (Expansion / Continuation)**
Used when institutions push price aggressively below the CRT dealing range.

* **Step 1 (Displacement Breakout)**: A 15-minute candle closes body-below the CRT Low with strong volume acceleration (RVOL > 1.5).
* **Step 2 (Retest)**: Price pulls back to retest the broken **CRT Low** or an open 5m FVG.
* **Step 3 (Entry)**: Enter Short on the retest of the broken CRT Low boundary.
* **Stop-Loss**: Placed above the 5m swing high inside the breakout leg.
* **Take-Profit**: Next major liquidity pool (Targeting 2:1 Minimum R:R).

---

## 4. How to Identify CRT Invalidation (When to Cancel / Void Setup)

A CRT setup is **invalidated immediately** if any of the following 5 conditions occur:

```
[INVALIDATION CHECKLIST]
[!] Off-Zone Violation: Trying to buy in Premium (>50%) or short in Discount (<50%).
[!] No Displacement: Sweep occurs but 5m chart drifts sideways with no CHoCH/FVG.
[!] Range Overrun: 15m body closes fully beyond the opposite CRT boundary.
[!] Equilibrium Stagnation: Price trapped inside 50% Equilibrium for >4 consecutive candles.
[!] High-Impact News: Event within 15 minutes (CPI, NFP, FOMC).
```

### **1. Off-Zone Execution Violation**
* **Trigger**: Attempting to execute a Long in the Premium Zone ($>50\%$) or a Short in the Discount Zone ($<50\%$).
* **Action**: **VOID TRADE**. Never enter a position against the zonal rule.

### **2. Lack of Displacement (The "Fake Sweep")**
* **Trigger**: Price wicks past the CRT High/Low, but the subsequent 5m candles drift sideways without creating a Change of Character (CHoCH) or Fair Value Gap (FVG).
* **Action**: **CANCEL LIMIT ORDER**. The lack of impulsive volume indicates smart money is not participating.

### **3. Benchmark Range Overrun**
* **Trigger**: After sweeping the CRT Low for a bullish reversal, price continues bleeding downward and a 15-minute candle closes completely below the lower invalidation buffer.
* **Action**: **VOID CRT**. The dealing range is broken; wait for the next 15m/1h candle to form a fresh benchmark range.

### **4. Equilibrium Midpoint Stagnation**
* **Trigger**: Price gets stuck oscillating around the **50% CRT Equilibrium** for more than 4 consecutive 5-minute candles without reaching either boundary.
* **Action**: **STAND DOWN**. Market is entering chop/consolidation.

### **5. Tier-1 News Distortion Window**
* **Trigger**: Any setup forming within 15 minutes before or after major economic news releases (CPI, NFP, FOMC, ISM).
* **Action**: **CANCEL ALL ORDERS**. News events generate artificial slippage and invalid price spikes.

---

## 5. Summary Cheat Sheet for Execution

| Step | Objective | Timeframe | Action |
| :--- | :--- | :--- | :--- |
| **1. Define CRT** | Identify High, Low, & 50% Midpoint | 15m / 1h | Plot CRT High/Low boundaries on chart. |
| **2. Wait for Sweep** | Watch for price to cross CRT boundary | 15m / 5m | Alert fires when CRT High or Low is swept. |
| **3. Confirm CHoCH** | Look for impulsive reversal + FVG | 5m | Confirm 5m Change of Character with FVG creation. |
| **4. Check Invalidation**| Verify Zonal & Displacement rules | 5m | Ensure Buy is in Discount (<50%) and no news. |
| **5. Execute POI** | Set Limit-Trap Order | 5m | Limit Order at 5m OB or 50% FVG. Set 2:1 R:R target. |
