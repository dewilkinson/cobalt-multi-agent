import os

report_content = """# Daily Trading Report - 2026-06-10

## Overview
- **Account**: Dave Wilkinson (Blueshell Securities LLC)
- **Closing Balance**: $100,541.12 (Based on Single-Day PNL)
- **Single-Day PNL**: $12.57

## Trading Activity
| Time | Symbol | Action | Quantity | Price | Total | Grade |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 09:35:35 | XLP | SELL | 150.0 | $84.855 | $12,728.25 | A |
| 10:37:23 | OCC | BUY | 100.0 | $26.9694 | $2,696.94 | A |
| 10:43:25 | OCC | SELL | 100.0 | $27.18 | $2,718.00 | A |
| 10:53:42 | XLP | BUY | 100.0 | $85.16 | $8,516.00 | B |
| 10:54:49 | XLP | BUY | 100.0 | $85.145 | $8,514.50 | B |
| 10:59:23 | DVN | BUY | 200.0 | $46.52 | $9,304.00 | C |
| 11:00:43 | DVN | SELL | 200.0 | $46.455 | $9,291.00 | C |
| 11:28:14 | DVN | BUY | 100.0 | $46.82 | $4,682.00 | C |
| 11:29:17 | DVN | BUY | 100.0 | $46.8199 | $4,681.99 | C |
| 11:31:57 | XLP | BUY | 100.0 | $85.54 | $8,554.00 | D |
| 11:32:53 | XLP | BUY | 100.0 | $85.54 | $8,554.00 | D |
| 11:41:44 | DVN | SELL | 200.0 | $46.695 | $9,339.00 | C- |
| 11:46:31 | XLP | SELL | 400.0 | $85.25 | $34,100.00 | C |
| 11:53:25 | DVN | BUY | 100.0 | $47.125 | $4,712.50 | D |
| 12:22:31 | DVN | SELL | 100.0 | $46.93 | $4,693.00 | D |

## Market & Scanner Context
The trading session on June 10, 2026, was characterized by defensive rotations in the morning followed by high volatility in energy and technology names. The scanner highlighted strong momentum setups, but the broader market context required caution as major indices faced overhead resistance. Under the "Shield" strategy, defensive sectors like Consumer Staples (XLP) offered excellent low-risk swing setups, which the user successfully capitalized on at the open. However, intraday volatility in commodities led to aggressive and ultimately unprofitable trades in Devon Energy (DVN) as breakout setups failed to sustain institutional volume.

The user's trading in OCC showed good tactical execution, utilizing a quick momentum scalp in a highly liquid setting. Conversely, the trading in DVN was plagued by execution drift. Although the scanner indicated institutional support for DVN, the entries were chased into minor extensions, resulting in immediate drawdowns and stop-outs. This session demonstrated the clear difference between structured swing accumulation and over-active intraday chasing.

## Summary of Moves
Overall, the day was a study in **Execution Drift vs. Swing Discipline**. The total PNL ended in a minor profit of **+$12.57** (realized profit of $12.57), but the execution quality was mixed. The swing trade close in XLP was executed with high discipline, capturing a clean overnight move. However, the afternoon sessions in DVN and XLP featured over-leveraging and chasing vertical extensions, eroding the morning's gains.

## Individual Trade Breakdown

### XLP
**Grade: B-**  
The morning exit at $84.855 of the 150 shares accumulated yesterday was highly disciplined, locking in **+$87.50** in profit. However, the afternoon trades were less controlled. The user bought 200 shares near $85.15 and then added another 200 shares at the local top of $85.54. Chasing the $85.54 level directly violated the "do not chase" protocol, and the subsequent liquidation at $85.25 resulted in a loss of **-$38.50** on the afternoon campaign.

### OCC
**Grade: A**  
A text-book scalp trade. The entry at $26.9694 was well-timed, and the exit at $27.18 locked in a quick profit of **+$21.06** with minimal exposure (6 minutes holding time). This trade showed excellent focus and discipline.

### DVN
**Grade: D**  
Devon Energy (DVN) was a clear case of over-trading. The user entered three separate campaigns:
1. Bought 200 shares at $46.52 and stopped out at $46.455 (Loss: **-$13.00**).
2. Bought 200 shares at $46.82 / $46.8199 and stopped out at $46.695 (Loss: **-$24.99**).
3. Bought 100 shares at $47.125 and stopped out at $46.93 (Loss: **-$19.50**).
Each campaign involved buying localized extensions rather than waiting for structural pullbacks to Fair Value Gaps (FVGs) or discount zones. Total loss realized on DVN was **-$57.49**.

## Execution Efficiency & SMC Audit
- **Entry Efficiency**: Low to Moderate. Morning setups were clean, but afternoon entries in DVN and XLP were consistently executed near local intraday resistance.
- **Exit Efficiency**: Moderate. Liquidations were swift when trades went against the user, preventing larger structural damage.
- **SMC Alignment**: Low in DVN. The user chased intraday breakout extensions rather than waiting for institutional discount block entries. High in the morning XLP exit.

## Performance Notes
- **Strategy Reflection**: The user attempted to trade defensive "Shield" assets like XLP with aggressive intraday scaling and chased DVN breakouts, turning a potentially highly profitable day into a near break-even session. Swing accumulation protocols must be followed strictly: entries belong in discount zones, not on breakout spikes.

---
*Generated by Cobalt Multiagent Journaler*"""

rolling_content = """# Trader Performance History

## Core Patterns & Reflection (As of June 10, 2026)
- **Recurring Mistakes**: Chasing breakout extensions in high-volatility names (e.g., DVN) and scaling in aggressively at local tops (e.g., XLP at $85.54).
- **Emotional Patterns**: "FOMO" behavior during mid-day sessions leading to multiple campaigns on stopped-out tickers instead of waiting for daily close or structural Fair Value Gaps (FVGs).
- **Strategy Adherence**: Mixed. High discipline on morning swing trade exits (XLP swing locked in +$87.50) and quick scalp execution (OCC +$21.06), but low discipline during intraday commodity breakouts.
- **Actionable Adjustments**: Limit intraday campaign attempts to a maximum of 2 per symbol. Establish a hard "no-chase" limit of 0.5% above daily strike zones.
"""

def main():
    # Targets
    paths = [
        "c:/github/obsidian-vault/Journals/Daily_Trading_Report_2026-06-10.md",
        "c:/github/obsidian-vault/Journals/Daily Reports/Daily_PostMortem_2026-06-10.md",
        "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/reports/performance/Daily_PostMortem_2026-06-10.md"
    ]
    
    for p in paths:
        dir_name = os.path.dirname(p)
        os.makedirs(dir_name, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"Wrote report to {p}")
        
    rolling_path = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/reports/performance/Trader_Performance_History.md"
    os.makedirs(os.path.dirname(rolling_path), exist_ok=True)
    with open(rolling_path, "w", encoding="utf-8") as f:
        f.write(rolling_content)
    print(f"Wrote rolling performance history to {rolling_path}")

if __name__ == "__main__":
    main()
