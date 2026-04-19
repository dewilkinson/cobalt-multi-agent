# Apex 500 Strategy: A Beginner's Guide

## What is the Apex 500?
The **Apex 500 Strategy** is a trading system built around **Smart Money Concepts (SMC)**. In simple terms, SMC is the strategy of tracking where giant institutions (like banks) are placing massive orders, rather than trading like a regular "retail" investor. The number one rule of the Apex 500 is **capital preservation**—protecting your money above making risky bets.

## Key Trading Terms & Lookback Periods

- **RVOL (Relative Volume)**: Measures today's trading volume against the historical moving average. 
  - *Lookback Period*: **10 Days**
  - *Formula*: $RVOL = \frac{V_{today}}{\frac{1}{10} \sum_{i=1}^{10} V_i}$
  - *Why it matters*: An RVOL > 2.0 confirms that institutions are urgently accumulating the stock today relative to the last 2 weeks.

- **Sortino Ratio ($S$)**: A performance metric that heavily penalizes downside drops. 
  - *Lookback Periods*: **Tactical (10–20 days)** to capture short-term regime shifts, or **Operational (60 days)** for full cycles. Default is **20 Days**.
  - *Formula*: $S = \frac{R_p - r_f}{\sigma_d}$ 
  - *(Where $R_p$ is the portfolio return, $r_f$ is the risk-free rate, and $\sigma_d$ is downside deviation).*
  - *Why it matters*: We require $S \ge 2.0$, ensuring we only interact with safe, upwardly stable assets.

- **ATR (Average True Range)**: The average range in price a stock historically covers.
  - *Lookback Period*: **Weekly (5 Days)** or **Rolling 20-Day**.
  - *Formula*: $ATR = \frac{1}{N} \sum_{i=1}^{N} TR_i$ *(Where TR is the daily high minus low)*.
  - *Why it matters*: We demand that our target profit rests comfortably within **1.5x** of the Weekly ATR, ensuring our goals are mathematically realistic.

- **Relative Strength (RS)**: Comparing the stock to the broader market.
  - *Lookback Period*: **Rolling 3-Months**.
  - *Why it matters*: A stock must show resilient RS > 90 over the entire last quarter to earn our capital.

## How the Strategy Enters a Trade
1. **Volume Spikes**: The system only allows aggressive buying (a **STRIKE**) if RVOL > 2.0. If RVOL is below 1.0, the market is completely asleep, and we **WAIT**.
2. **The "Stop Hunt"**: The system waits for moments when a stock price temporarily tricks regular traders into selling (a "Stop Hunt"), before immediately reversing upward.

## The Macro Compass
- **Aggressive Mode**: If the VIX is low (`< 23`) and interest rates (.TNX) are calm, we buy fast-growing companies.
- **Defensive Mode**: If the VIX shoots above 25, or interest rates jump above 4.30%, the strategy refuses to buy high-risk stocks. Under Yield-Spikes (.TNX > 4.30%), our Sortino standard hikes even tighter to $S \ge 2.5$.

## Catalyst & Execution Grading
Even if a stock exhibits perfect technical alignment, it is structurally capped as a **"B+" Grade** setup if there is no underlying narrative reason for the movement.

To elevate a trade into the premier **"A"**, **"A+"**, or **"S"** strategy tiers, it must be fueled by a tangible **Catalyst**. This typically means actual breaking news hitting the wire, but it can also include highly bullish institutional reports or surging social media sentiment.
