# Risk Management Protocol: A Beginner's Guide

## Why Risk Management Matters
Even the best traders in the world only win about 50% to 60% of their trades. **Risk Management** is the mathematical secret to extracting overall wealth from the market even when you fail half the time. This document is the ultimate master law of the system.

## The "R" Concept (The Risk Unit)
We use a concept called **"R"** (Risk Unit) to standardize our bets. 
- In a $\$100,000$ account, **1R** is strictly defined as **$\$250$** (or $0.25\%$ of the total asset base).
- **The Golden Rule**: Every trade is structurally built so that if our premise is entirely wrong and we hit our emergency stop, we lose exactly $1R$.

## Position Sizing Equation
We do not randomly buy "100 shares" of a stock. We use a precise algebraic formula:
$\text{Shares} = \frac{R}{\text{Entry Price} - \text{Stop Loss Price}}$

*Example:* 
If you want to buy a stock entering at $\$20.00$, and the nearest foundational Order Block defines your true Stop Loss at $\$18.00$:
- $\text{Gap Risk} = \$20.00 - \$18.00 = \$2.00$
- $\text{Shares} = \frac{\$250}{\$2.00} = 125 \text{ shares}$
If the stock completely collapses below $\$18.00$, the system will liquidate your 125 shares for a total systemic hit of exactly $\$250$ (1R).

## Maximum Account Risk Constraint
$\sum_{i=1}^{N} \text{Active Risk}_i \le 2\% \times \text{Total Asset Base}$
- At any given time, the cumulative raw risk of all actively open trades cannot logically exceed 2% of your entire portfolio. You are statistically protected against "blowing up" your account.

## Risk Tiers: When to Bet Light vs Heavy
- **The SCOUT Unit ($0.5R$)**: We risk exactly half our base unit ($\$125$) during morning volatility windows (9:30 AM – 10:15 AM) or when overall market sentiment is overwhelmingly hostile ($VIX > 26$).
- **The PROBE Unit ($0.5R$)**: A dedicated transitional tier. When the market is elevated but not paralyzed ($VIX$ between $24$ and $26$), the strategy stays active but the Risk Manager mathematically forces all trades down to $\$125$ to systematically "test the waters."
- **The STRIKE Unit ($1.0R$)**: Our confident, full deployment ($\$250$) when the market is calm ($VIX < 24$) and institutions are heavily buying ($RVOL > 2.0$). 

## The Failsafes 
If things go wrong, the AI activates rigid circuitry:
1. **The Daily Shutdown (3R Stop)**: If you acquire 3 standard losses in a single day ($\sum \text{Daily Losses} = 3R$), all autonomous evaluation systems shut down. You are done for the day.
2. **The Tilt Protocol**: A sequence of three cumulative losses forces all your future deployments to instantly shrink down to cautious $0.5R$ Scout sizes until you regain baseline rhythm.
3. **MOC (Market on Close) Liquidations**: The market closes at 4:00 PM EST. If it's 3:55 PM and the VIX is structurally pinned above $25$, the system automatically liquidates weak equities at Market on Close (MOC) to secure capital overnight.
