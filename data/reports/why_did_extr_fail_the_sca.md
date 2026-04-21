# 1. Execution Summary

**REJECTED**. Extreme Networks (`EXTR`) has been disqualified from the Sortino Sniper scan due to three critical structural violations involving supply overhang, valuation drift, and relative strength lag. While the intraday price action and volume appear healthy for a retail setup, the stock has grown beyond the "asymmetric velocity" parameters defined in your **Blueshell Securities** institutional mandate.

The failure is primarily driven by the **Float Constraint** and **Market Cap Ceiling**. In our IRA-specific "Sword and Shield" framework, we target stocks that require less capital to move aggressively. `EXTR` is currently "too thick," meaning it requires significantly more institutional displacement to achieve a `3:1` Reward-to-Risk (RR) outcome within a standard weekly ATR. Proceeding with stocks of this size increases our downside deviation ($\sigma_d$), directly threatening our required Sortino Ratio of `2.0`.

---

### **TECHNICAL AUDIT: SCAN FAILURES**

The following metrics represent the "Ground Truth" data points that triggered the system veto:

*   **Float Volume**: `129.4M` shares 
    *   **Hurdle**: `20M` – `100M` 
    *   **Status**: **FAIL** (Excess supply dilutes institutional displacement).


*   **Market Capitalization**: `$2.46B` 
    *   **Hurdle**: `$300M` – `$2.0B` 
    *   **Status**: **FAIL** (Valuation has drifted into stabilized Mid-Cap territory).


*   **Relative Strength (RS)**: `89` 
    *   **Hurdle**: `> 90` 
    *   **Status**: **FAIL** (Lacks top-tier alpha leadership for a long-only IRA).


*   **Current Price**: `$19.17` 
    *   **Hurdle**: `$10.00` – `$50.00` 
    *   **Status**: **PASS**


*   **Momentum Gap**: `3.62%` 
    *   **Hurdle**: `+3%` to `+8%` 
    *   **Status**: **PASS**

---

### **STRATEGIC RATIONALE**

**The "Thick Float" Trap**
With a float of `129.4M` shares, `EXTR` requires significantly more "Smart Money" accumulation to create a Change of Character (**CHoCH**) that sticks. For your sniper strategy, we prioritize symbols where `RVOL > 2.0` can easily clear the order book. This stock’s current float is `29.4%` above our maximum threshold, leading to "choppy" price discovery that often triggers stops before reaching `3R` targets.

**Alpha Sensitivity**
An RS rating of `89` indicates that while `EXTR` is outperforming a majority of the market, it is not in the "lead horse" category. In a **War Barbell** configuration, "Swords" must be the absolute leaders (`RS > 90`) to ensure they recover quickly from market-wide dips.

**Sortino Protection**
Our mandate is to minimize downside deviation. Larger market-cap stocks like `EXTR` (`$2.46B`) tend to exhibit more institutional "grinding" rather than the "snapping" momentum we require. This grinding action lowers the Sortino Ratio by increasing the time spent in minor drawdowns.

---

### **EXECUTION PARAMETERS (RESTRICTED)**

| Parameter | Value | Status |
| :--- | :--- | :--- |
| **Execution State** | **NO TRADE** | **Authorized** |
| **Risk Unit (R)** | `$250` | Deactivated |
| **Share Quantity** | `0` | Restricted |
| **Strike Zone** | `N/A` | No Entry |
| **Hard Stop** | `N/A` | No Entry |

**Note for Dave**: I recommend maintaining strict adherence to the `$2.0B` cap. As symbols move into Mid-Cap territory, they transition from "Swords" to "Shields," but `EXTR` does not currently offer the low-volatility profile required for a "Shield" position. We will wait for the next morning scan to identify high-velocity candidates within the `20M` – `100M` float sweet spot.