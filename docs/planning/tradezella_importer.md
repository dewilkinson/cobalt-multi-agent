# Implementation Plan: TradeZella Importer Reconciliation Engine

Automate the detection of trade chronology to ensure all day-trades are sequenced as "Long" (Buy before Sell) and implement a historical lookback to resolve orphaned swing trades.

## Design Decisions
- **Live Document Policy**: This document serves as the single source of truth for the TradeZella importer feature set.
- **Execution Splitting**: To maintain strict FIFO parity in TradeZella, the Lookback engine splits large historical executions, cloning the row and pulling only the exact `Quantity` needed to resolve a deficit.
- **`--reconcile` Flag**: Implements a "Session-Aware" lookback engine that automatically resolves orphaned trades by backfilling entries from historical data.
- **Long-Only Heuristic**: In an IRA account, we definitively assume that no "Sell to Open" (Short) trades exist. The tool will automatically flip the order for any symbol where the session net goes negative in the original file sequence.
- **Orientation Detection**: Robustly handles inconsistent "Newest-to-Oldest" and "Oldest-to-Newest" broker exports.

## User Review Required
> [!IMPORTANT]
> **Stitching Logic**: The `--reconcile` flag will "reach back" into the full `Accounts_History` file to find matching entries for any symbol that appears "orphaned" in your filtered date range. If an entry cannot be found, the symbol will be safely removed from the export to protect your TradeZella data integrity.

## Proposed Changes

### ️ CSV Processor Refactor
#### [MODIFY] [csv-to-tradezella.py](file:///c:/github/cobalt-multi-agent/tools/csv-to-tradezella/csv-to-tradezella.py)
*   **Lookback Engine (Execution Splitting)**: Implement a reverse-chronological search through `all_trades_by_date` to backfill missing entries for unresolved trades. Dynamically splits bulk historical executions to fulfill exact share deficits without generating phantom open trades.
*   **Time Filtering**: Supports automated start dates via `--week`, `--month`, and `--ytd` (Year-to-Date) flags.
*   **CLI Integration**: Add the `--reconcile` switch to activate the Lookback Engine.
*   **Audit Dashboard UI**: Dynamic timestamping parsing to display the active dataset range directly in the UI Title and Subtitle.

## Verification Plan

### Automated Tests
- Run `python csv-to-tradezella.py --range 2026-04-01 2026-04-09 --reconcile`.
- Verify that **04/09** (Today) results in Morning Buys coming first.
- Verify that **03/30** (Historical) entries are correctly backfilled for any April exits.

### Manual Verification
- Review the Audit Dashboard to confirm no "Short" trades are erroneously reported.
