# VibeLink Interface (VLI) - User Guide

The VibeLink Interface (VLI) is the user-facing command layer for **Project Cobalt**. It translates natural language "vibes" into high-fidelity financial dispatches.

## Interacting with the CMA

Project Cobalt uses specialized agents (Scout, Analyst, Researcher, Journaler) to fulfill your requests. 

### 1. Direct Data Fetching (The Scout)
Ask for raw data, such as:
- *"Show me my current Binance balances."*
- *"Fetch my Trade History for the last 30 days."*
- *"Get the current quote for NVDA."*
- *"Crawl the latest 10-K report for Apple."*

### 2. High-Fidelity Analysis (The Analyst)
Request structured technical indicators:
- *"Perform an SMC analysis on BTC/USD."*
- *"Show me the Volume Profile and POC for ETH."*
- *"Are there any Fair Value Gaps (FVG) on the 4H chart for SPY?"*
- *"Calculate the Bollinger Bands and ATR for TSLA."*

### 3. Integrated Synthesis (The Researcher)
When you need context beyond pure charts:
- *"What's the macro sentiment for the DXY this week?"*
- *"Search for any major news affecting the semiconductor sector."*
- *"Compare the technical EMA trends of MSFT with its latest earnings results."*

### 4. Direct Response (Fast Bypass)
For trivial questions, the system provides a **Fast Bypass** for instant answers:
- *"What is 2+2?"*
- *"What is the price of Gold?"*

## Output Formats (Dispatches)

By default, the system delivers findings as **Dispatches** to your local Obsidian vault.

- **Technical Dispatches**: strictly formatted Markdown tables with zero conversational filler.
- **Research Dispatches**: comprehensive summaries with bulleted findings and source citations.
- **Journal Dispatches**: Trading logs and account snapshots archived for auditability.

## Customizing your VLI

You can customize the "vibe" and thresholds of your analysis in the `conf.yaml` file, specifying:
- **Verbosity Levels** (0: Zero-Filler to 3: Deep Commentary).
- **Default Lookback Periods** (e.g., 1 day for technicals, 30 days for macro).
- **Agent Personalities**.
