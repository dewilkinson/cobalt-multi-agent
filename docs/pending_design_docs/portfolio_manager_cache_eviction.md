# Portfolio Manager Cache Eviction Architecture

## Overview
Currently, the VLI system features a robust `invalidate cache` command that targets the `DatastoreManager` (AI Analysis and Symbol Reports). However, the recently implemented `BrokerageCache` (`data/brokerage_cache.json`), which stores historical portfolio manager trade executions via SnapTrade, operates on a completely independent storage layer. 

As a result, issuing an `invalidate cache` command does not clear the BrokerageCache. We need dedicated routing hooks and system commands to allow administrators to forcibly clear the portfolio trade history cache.

## Proposed Implementation

### 1. Intent Parser Updates
The AI Intent Parser needs to be updated to distinguish between standard Datastore cache eviction and Portfolio/Brokerage cache eviction.
- Expand `_get_vli_intent(text)` to detect variations like:
  - `"clear portfolio cache"`
  - `"evict brokerage cache"`
  - `"force sync order history"`

### 2. Backend Routing Hooks (`app.py`)
Add a new intent hook in the primary execution flow of `backend/src/server/app.py`:

```python
if intent_mode == "EVICT_BROKERAGE_CACHE" or "portfolio cache" in request.text.lower():
    try:
        from src.services.brokerage_cache import BrokerageCache
        BrokerageCache.clear_all()  # Or pass a specific account_id
        res_msg = "Portfolio Manager cache has been successfully evicted. The next dashboard load will perform a full historical sync."
    except Exception as e:
        res_msg = f"Failed to evict Portfolio Manager cache: {e}"
        
    _append_to_vli_history("ai", res_msg, thread_id=transaction_id)
    return {"response": res_msg, "status": "OK", "error_details": None, "thread_id": transaction_id}
```

### 3. BrokerageCache Class Updates (`backend/src/services/brokerage_cache.py`)
Introduce a class method to handle the physical deletion of the cache file or targeted wiping of an `account_id` key.

```python
@classmethod
def clear_all(cls) -> None:
    """Wipes the entire brokerage cache from disk."""
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
        logger.info("[BROKERAGE_CACHE] Cache file permanently deleted.")

@classmethod
def clear_account(cls, account_id: str) -> None:
    """Wipes the cache for a specific account."""
    cache = cls._load_cache()
    if account_id in cache:
        del cache[account_id]
        cls._save_cache(cache)
        logger.info(f"[BROKERAGE_CACHE] Cleared cache for account {account_id}.")
```

### 4. VLI Dashboard UI 
While the user can trigger this via a chat command (`clear portfolio cache`), it may also be prudent to add a `[Clear Portfolio Cache]` administrator button to the System Settings panel in the Web Dashboard, matching the `Force Resync` checkbox found in the Python GUI.
