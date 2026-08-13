# Cobalt DSV Pine Script Indicator Design Specification

**Document Version**: 1.0.0  
**Target Platform**: TradingView (Pine Script v5)  
**Strategy Alignment**: Dual-Session Vector (DSV) Strategy  
**Location**: `specs/dsv_pine_indicator_design_spec.md`

---

## 1. Overview & Objective

The **Cobalt DSV Indicator** packages the essential components of the **Dual-Session Vector (DSV)** strategy into a unified, clean TradingView Pine Script v5 indicator. It eliminates chart clutter by consolidating session benchmark bounds, Candle Range Theory (CRT) 50% equilibrium levels, Fair Value Gap (FVG) detection, and SMT correlation markers into a single overlay.

---

## 2. Technical Architecture & Input Parameters

### 2.1 Core Inputs
```pinescript
// Session Inputs
var string i_asiaSession   = input.session("1800-0200", "Asian Session (EST)", group="Session Setup")
var string i_londonSession = input.session("0200-0800", "London Session (EST)", group="Session Setup")
var string i_nySession     = input.session("0800-1700", "NY Session (EST)", group="Session Setup")

// Risk & Target Parameters
var float  i_riskAmount    = input.float(50.0, "Risk Per Trade ($)", group="Risk Engine")
var float  i_rrRatio       = input.float(2.0, "Target R:R Ratio", group="Risk Engine")
var int    i_microContracts= input.int(1, "Micro Contracts (MNQ/MES/M2K)", group="Risk Engine")

// Feature Toggles
var bool   i_showCRT       = input.bool(true, "Show CRT 50% Equilibrium", group="Visual Toggles")
var bool   i_showFVG       = input.bool(true, "Highlight 5m Fair Value Gaps", group="Visual Toggles")
var bool   i_showSMT       = input.bool(true, "Plot SMT Divergence Markers", group="Visual Toggles")
```

---

## 3. Core Functional Modules

### Module 1: Session Range & Benchmark Engine
* **Asian Session Range (18:00 – 02:00 EST)**:
  * Automatically tracks and draws **Asian High ($AH$)** and **Asian Low ($AL$)**.
  * Calculates and plots **Asian Equilibrium ($50\%\text{ EQ} = \frac{AH + AL}{2}$)** as a dashed line.
* **Midnight Open Benchmark**:
  * Draws a solid reference line at the **00:00 EST Candle Open**.

### Module 2: CRT Multi-Timeframe Stack
* Calculates 15m, 1h, and 4h Candle Range Theory (CRT) boundaries ($C_{High}$, $C_{Low}$, $50\%\text{ EQ}$).
* Fills discount (< 50% EQ) and premium (> 50% EQ) zones with semi-transparent HSL color overlays.

### Module 3: Market Structure Shift (MSS) & FVG Engine
* **5m FVG Detection**: Identifies 3-bar displacement gaps ($\text{Low}_{\text{bar3}} > \text{High}_{\text{bar1}}$ for bullish FVG; $\text{High}_{\text{bar3}} < \text{Low}_{\text{bar1}}$ for bearish FVG).
* **MSS Signal**: Triggers a `BUY` alert on 5m displacement over recent swing high/low following a session sweep.

### Module 4: Inter-Market SMT Correlation Marker
* Fetches correlated tickers (`NQ1!`, `ES1!`, `RTY1!`) using `request.security()`.
* Plots SMT Divergence markers (`▲ SMT BULL` / `▼ SMT BEAR`) when one index sweeps session extreme while the correlated index makes a higher low / lower high.

---

## 4. Visual Layout Mockup

```
   [Asian Range High (AH)] ------------------------------------------- (Red Line)
   
        [5m Bearish FVG Zone] ===== (Light Red Shaded Box)
   
   [Asian 50% Equilibrium] - - - - - - - - - - - - - - - - - - - - - - (Cyan Dashed)
   
        [5m Bullish FVG Zone] ===== (Light Green Shaded Box)
   
   [Asian Range Low (AL)] -------------------------------------------- (Green Line)
   
   [Midnight Open (00:00 EST)] ======================================== (White Solid)
```

---

## 5. Alert Conditions

```pinescript
alertcondition(bullishMSS, title="DSV Bullish Trigger", message="DSV: 5m Bullish MSS + FVG Retest Detected on {{ticker}}")
alertcondition(bearishMSS, title="DSV Bearish Trigger", message="DSV: 5m Bearish MSS + FVG Retest Detected on {{ticker}}")
alertcondition(smtDivergence, title="DSV SMT Divergence", message="DSV: SMT Divergence Sweep Confirmed between NQ / ES")
```
