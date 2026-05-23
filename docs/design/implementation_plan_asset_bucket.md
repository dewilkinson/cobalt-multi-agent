# Implementation Plan: Asset-Bucket Engine (Core Resource)

This plan outlines the integration of the **Asset-Bucket Engine**, shifting from hard-coded watchlists to dynamic, stateful asset containers that automate specific sequences of Cobalt financial operations.

## Goal
To implement `AssetBucket` as a robust, asynchronous component within the Cobalt backend architecture. It will take the user's provided specification and significantly upgrade it to support concurrent execution of real financial tools (`get_stock_quote`, `get_smc_analysis`, etc.), ensuring efficient batch processing of asset groupings.

## Proposed Changes

### `src/services/`
#### [NEW] `C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/services/asset_bucket.py`
This will house the core `AssetBucket` class engine.
*   **Upgrades from Spec:**
    *   **Asynchronous Engine:** `update()` and `_execute_op()` will be converted to `async def` and utilize `asyncio.gather` for concurrent fetching across the `assets` list to minimize latency.
    *   **Real Tool Integration:** The mock `_execute_op` will be hooked up to actual tools from `src.tools.finance`, translating user-friendly operations (e.g., `QUOTE`, `SMC_SCAN`, `RSI`) to the respective `async` tools.
    *   **Robust Telemetry / Error Handling:** Each asset evaluation will be wrapped in a `try/except` block to ensure that a failure on a single ticker (e.g., rate-limiting, bad symbol) does not crash the entire bucket update.
    *   **Path Resolution:** Will utilize `os.path.join(vault_path, ...)` but hook into Cobalt's environment configuration for reliable dynamic resolution if possible.

## Data Schemas and Supported Operations
By default, we will map the following `operations` strings to Cobalt backend tools:
*   `QUOTE` -> `get_stock_quote()`
*   `SMC_SCAN` -> `get_smc_analysis()`
*   `RSI` -> `get_rsi_analysis()`
*   `MACD` -> `get_macd_analysis()`
*   *(More can be added easily, but these serve as the foundation)*

## Open Questions
> [!WARNING]
> 1. **Scheduler Trigger:** The specification notes `"Registration: The bucket registers its intent with the External Scheduler."` Do you want me to hook the bucket's periodic modes into the existing `app.py` FastAPI `background_tasks` or `inbox_watcher` loop? Or should I strictly build the Engine class first and leave scheduling for later?
> 2. **Vault Path Guarantee:** I will default the `vault_path` to pull from your system environment `OBSIDIAN_VAULT_PATH` (`C:\github\obsidian-vault`) if it exists, otherwise fallback to the current dir. Is this acceptable?

## Verification Plan
### Automated Testing
*   Create a standalone script `backend/scratch/test_asset_bucket.py` that initialized an `AssetBucket` ("TEST_01", "Beta Tech"), adds `NVDA` and `AAPL`, assigns `["QUOTE", "RSI"]` ops, and calls `await update()`. We will verify it writes correctly to the expected `01_Transit/Buckets/TEST_01_state.json` file.
