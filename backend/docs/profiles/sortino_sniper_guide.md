# Sortino Sniper Strategy: A Beginner's Guide

## What is the Sortino Sniper?
The **Sortino Sniper** is a hyper-focused strategy that specifically targets highly liquid stocks priced precisely between **$10 and $50**. This isolates established Mid-Caps while dodging the erratic manipulation of "penny stocks."

## Mathematical Parameters & Core Metrics 

- **The Valuation Filter**: 
  - **Float**: $20,000,000 \le \text{Shares Available} \le 100,000,000$ (Guarantees strong liquidity but allows for large percentage moves).
  - **Market Cap**: $\$300M \le \text{Value} \le \$2B$ (Mid-Cap range).
  - **Daily Volume**: $> 1,000,000$ shares transacted by exactly 10:30 AM ET.

- **The Sortino Skew ($S$)**: 
  - *Lookback*: **20-Day Tactical Window**.
  - *Formula*: $S = \frac{R_p - r_f}{\sigma_d} \ge 2.0$ 
  - *Explanation*: We absolutely demand that the downside deviation ($\sigma_d$) remains mathematically low over the last 20 days. The stock must recover gracefully from red days.

- **Relative Strength (RS)**: 
  - *Lookback*: **3-Month Rolling Window**.
  - *Explanation*: The asset's rating against the S&P 500 must hold solidly at $RS > 90$ throughout a full financial quarter.

- **Trailing Momentum Exit (EMA)**: 
  - *Lookback*: **9-Period on the 5-Minute Chart**.
  - *Formula*: $EMA_{t} = V_t \times \frac{2}{N+1} + EMA_{t-1} \times (1 - \frac{2}{N+1})$
  - *Explanation*: When you take initial profits, the remaining shares dynamically ride the 9 EMA until the 5-minute candle officially breaks and closes below the curve.

- **Chaikin Money Flow (CMF)**:
  - *Lookback*: **20-Period on the 5-Minute Chart**.
  - *Rule*: CMF must be $> 0$ (ideally $> 0.05$ and rising) at the time of entry to confirm active institutional accumulation.

## Pillar 2 & 3: Finding the Entry
We execute everything on the **5-minute chart**, which filters out chaotic 1-minute tracking noise while still catching massive orders in real-time. We wait for very specific "footprints" left behind by hedge funds:
- **CHoCH (Change of Character)**: The exact moment price breaks a structural level and reverses out of a fakeout drop. This is our primary trigger, proving Smart Money is driving the price back up. (Maximum Profit Potential).
- **BoS (Break of Structure)**: When price breaks a high in an *already established* uptrend. We use this to confirm we are right, or to add more shares later.
- **Fair Value Gap (FVG)**: When institutions buy massive amounts of stock at once, the price rockets upward so fast it leaves an "empty gap." We wait patiently for the price to fall back and touch that gap before we buy.
- **Order Block (OB)**: The exact price floor where the massive institutional order was physically placed.
- **The Execution Sequence**: Sweep -> CHoCH (Trigger) -> Return to FVG (Entry) -> BoS (Confirmation).
- **TV Alert Entry Trigger**: Set a TradingView alert on the 5m timeframe for a BoS or CHoCH on daily candidates. Using these structural events as alert triggers ensures you can execute entries at a better price.

## Pillar 6: Swords and Shields
Instead of guessing our risk, we mathematically match our portfolio to the market weather:
- **Swords**: Fast-moving growth stocks. Highly aggressive. 
- **Shields**: Safe, boring assets or inverse funds. Highly defensive.
- **The Rule**: When VIX < 22, we hold **70% Swords**. When VIX > 26 (panic), we hold **80% Shields** to heavily defend our portfolio from drawdowns.

## Taking Profits
- **Scaling Out**: When we reach our targeted **3R** profit zone (which must fit cleanly within the 1.5x Weekly ATR), we instantly sell **75%** of our shares to secure a net positive return on the trade. We then move our Stop Loss to our exact entry price (Break-Even) and let the remaining **25%** ride on house money. This puts the position firmly in the green with an immensely high probability of sustained momentum.

## Catalyst & Execution Grading
Even if a stock exhibits perfect technical alignment, it is structurally capped as a **"B+" Grade** setup if there is no underlying narrative reason for the movement.

To elevate a trade into the premier **"A"**, **"A+"**, or **"S"** strategy tiers, it must be fueled by a tangible **Catalyst**. This typically means actual breaking news hitting the wire, but it can also include highly bullish institutional reports or surging social media sentiment.
