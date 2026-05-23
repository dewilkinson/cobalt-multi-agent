# Implementation Plan for Macro Watchlist Asset-Bucket

This plan outlines the steps required to implement the "Unified Asset-Bucket Specification" specifically for the Macro Watchlist, upgrading it to a "watchlist" class bucket with decoupled update frequencies and background queueing.

## Proposed Changes

### `C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/tools/`
#### [MODIFY] `finance.py`
Build new distinct tool to fulfill the macro-bucket requirements.
*   **`CALC_REGIME`**: Maps to a new `get_macro_regime(ticker)` async tool. It will check the latest price against basic thresholds (e.g., if `$VIX` > 20 return "STRESS", otherwise "NORMAL").

### `C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/src/services/`
#### [MODIFY] `asset_bucket.py`
Upgrade the Asset-Bucket engine to evaluate "watchlist-class" features, multi-frequency operation scheduling, and background prioritization constraints.
*   Update `load_config` and `_sync_with_external_scheduler` to properly handle operation-specific intervals (e.g., 1 minute for Price/Volume, 5 minutes for OHCL/SMC).
*   Add `FETCH_PRICE` (fast execution) to explicitly fetch just Price and Volume. 
*   Add `FETCH_OCHL` (cached execution) mapped directly to the existing `get_smc_analysis` tool in `smc.py`. This mirrors the identical timeframe and cache mechanisms already in use for other asset payloads.
*   **Queue Priority**: Update `_sync_with_external_scheduler` to register tasks with the specified `priority` field (e.g., passing `PRIORITY_BACKGROUND` to the scheduler to ensure lazy evaluation and prevent blocking primary workloads).
*   Implement safe parsing mechanisms to translate `$VIX` to `^VIX`, `.TNX` to `^TNX`, before dispatching.

### `c:/github/obsidian-vault/`
#### [NEW] `_cobalt/06_Resources/Buckets/MACRO_WATCHLIST_config.json`
Create the default JSON configuration with the expanded macro list, dual-frequency scheduling, and priority fields.
```json
{
    "bucket_id": "MACRO_WATCHLIST",
    "display_name": "Macros",
    "bucket_class": "watchlist",
    "priority": "PRIORITY_BACKGROUND",
    "assets": ["$VIX", ".TNX", ".DXY", "SPY", "QQQ", "CL=F", "GC=F"],
    "operations": {
        "FETCH_PRICE": {"interval": 1},
        "FETCH_OCHL": {"interval": 5},
        "CALC_REGIME": {"interval": 5}
    },
    "update_mode": "PERIODIC",
    "display_columns": ["Ticker", "Price", "Volume", "Regime"]
}
```

## Verification Plan

### Automated Tests
1. Test operation mapping in `_execute_op` for `FETCH_PRICE`, `FETCH_OCHL` (calling `get_smc_analysis`), and `CALC_REGIME`.
2. Verify the `CALC_REGIME` tool evaluates correctly for `$VIX`.
3. Verify that the `_sync_with_external_scheduler` mock output correctly acknowledges `PRIORITY_BACKGROUND` for `MACRO_WATCHLIST`.
4. Manually trigger `await monitor.update()` in a test loop to confirm the engine correctly skips 5-minute operations if 5 minutes have not passed.
