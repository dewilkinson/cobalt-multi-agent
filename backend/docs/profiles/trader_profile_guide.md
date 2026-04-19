# Trader Persona: A Beginner's Guide

## Core Identity
**Role**: Expert Stock Analyst & Risk Manager.
The AI operates your portfolio based entirely on hard math, eliminating human emotion, fear, and greed. 

**"Long-Only IRA"**: This means the persona operates a retirement account that can only make money when stocks go *UP* (going "Long"). We cannot "short sell" (borrowing shares to bet against a company), and we never use borrowed money.

## The Mathematical Trading Styles
The AI can seamlessly switch its tempo depending on the market, calculating expectancies algebraically ($E = (\text{WinRate} \times \text{AvgWin}) - (\text{LossRate} \times \text{AvgLoss})$):
1. **The Sniper**: Extremely patient. 
   - *Parameters*: $40\%$ Strategy Win-Rate | $4:1$ Reward-to-Risk. 
   - *Pacing*: ~5 Trades a week. 
2. **The Grinder (Default)**: Steady and reliable.
   - *Parameters*: $50\%$ Strategy Win-Rate | $3:1$ Reward-to-Risk. 
   - *Pacing*: ~5 Trades a week. 
3. **The Hi-Freq**: Much more active. 
   - *Parameters*: $60\%$ Strategy Win-Rate | $2:1$ Reward-to-Risk. 
   - *Pacing*: ~7 Trades a week. 

## The Core Metric: Sortino Ratio
The ultimate compass for the Persona is the **Sortino Ratio ($S$)**.
$S = \frac{R_p - r_f}{\sigma_d}$
- **Lookback Period**: Default evaluates the last **20 Trading Days** (roughly one calendar month) to judge the stock's recent behavior. 
- **The Math**: If a trader makes a lot of money ($R_p$) but forces you to endure terrifying, volatile drops ($\sigma_d$), $S$ plummets. We enforce a strictly conservative constraint: **$S \ge 2.0$**. The profile literally cannot buy structurally chaotic stocks.

## Volume Lookback (RVOL)
The persona relies on Relative Volume to verify institutional presence:
$RVOL = \frac{V_{today}}{\frac{1}{10} \sum_{i=1}^{10} V_i}$
- **Lookback**: **10 Trading Days**. RVOL simply divides today's volume by the average daily volume of the last two weeks.

## Dealing with Market Events
The market occasionally goes crazy on scheduled dates. We call these "Catalysts":
- **FOMC**: The U.S. Federal Reserve releasing interest rate decisions. 
- **Quad Witching**: Expirations of stock options contracts.
- **FDA Decisions**: Pharmaceutical approvals or rejections.

*Rule*: To protect your money, we universally exit high-risk positions by 3:55 PM ET the day *before* these events occur.
