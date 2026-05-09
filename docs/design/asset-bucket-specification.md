#inbox #cobalt #scripts 

# Project Cobalt: Asset-Bucket Specification (Resource Type)
## 1. Concept Overview
The **Asset-Bucket** is a modular container designed to manage groups of assets (Stocks, ETFs, Crypto) and automate the application of "Operation Sequences" to them. It replaces hard-coded watchlists with dynamic, stateful objects that can be visualized and updated independently.
## 2. Structural Components
| Property | Description |
|---|---|
| **ID / Bucket ID** | Unique alphanumeric identifier for filesystem/internal logic (e.g., TECH_TRIAD). |
| **Display Name** | String field for user-friendly UI labeling (e.g.,  High-Beta Tech Leaders). |
| **Asset List** | A dynamic array of tickers. |
| **Operations** | A sequence of Cobalt Tools to run (e.g., [FETCH_QUOTE, RUN_SMC, GET_SENTIMENT]). |
| **Update Mode** | MANUAL, ONE_SHOT, or PERIODIC. |
| **Interval** | Time in minutes. For PERIODIC, this is the frequency. For ONE_SHOT, this is the delay before the single trigger is fired. |
| **Display Columns** | User-defined data fields for visualization (e.g., Price, SMC_Trend, Vibe). |
## 3. Workflow & Integration
 1. **Initialization:** User defines a bucket and assigns the assets.
 2. **Registration:** The bucket registers its intent with the **External Scheduler**.
   * If PERIODIC: Scheduler sets a recurring timer.
   * If ONE_SHOT: Scheduler sets a single timer to fire after interval minutes.
 3. **Execution:** When triggered, the bucket iterates through its assets and executes the Operation Sequence.
 4. **Persistence:** Results are saved to 01_Transit/Buckets/[Bucket_ID].json.
## 4. Asset-Bucket Engine (Source Code)
```python
"""
PROJECT COBALT: CORE RESOURCE TYPE
RESOURCE: Asset-Bucket Engine
VERSION: 1.1.0

PROBLEM STATEMENT:
    Traders need to bundle assets and apply specific logic sequences at specific 
    times. A 'watchlist' needs a simple quote every 5m, while an 'intelligence 
    briefing' needs a deep SMC/Sentiment scan once every 24h.

UPDATES IN V1.1.0:
    - Added 'display_name' field for enhanced UI metadata.
    - Updated 'interval' logic to support delay-based 'ONE_SHOT' triggers.
"""

import json
import os
from datetime import datetime

class AssetBucket:
    def __init__(self, bucket_id, display_name, vault_path="./"):
        self.bucket_id = bucket_id
        self.vault_path = vault_path
        self.config_path = os.path.join(vault_path, f"06_Resources/Buckets/{bucket_id}_config.json")
        self.state_path = os.path.join(vault_path, f"01_Transit/Buckets/{bucket_id}_state.json")
        
        # Default Configuration
        self.config = {
            "bucket_id": bucket_id,
            "display_name": display_name,
            "assets": [],
            "operations": ["QUOTE"],
            "update_mode": "MANUAL",
            "interval": 60, # Frequency for periodic; Delay for one-shot
            "display_columns": ["Ticker", "Price", "Change %"]
        }
        self.load_config()

    def load_config(self):
        """Loads configuration from the vault if it exists."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                self.config.update(json.load(f))

    def save_config(self):
        """Persists bucket configuration and triggers scheduler sync."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)
        self._sync_with_external_scheduler()

    def _sync_with_external_scheduler(self):
        """
        Placeholder for communicating with an external scheduler (like Celery/APScheduler).
        Registers the timer based on update_mode and interval.
        """
        mode = self.config["update_mode"]
        interval = self.config["interval"]
        
        if mode == "PERIODIC":
            print(f" Scheduler: Registering recurring task for {self.bucket_id} every {interval}m.")
        elif mode == "ONE_SHOT":
            print(f"️ Scheduler: Registering single trigger for {self.bucket_id} in {interval}m.")

    def update(self):
        """Iterates through assets and applies the operation sequence."""
        print(f" Updating Bucket: {self.config['display_name']}...")
        results = {}
        
        for asset in self.config["assets"]:
            asset_results = {"Ticker": asset}
            for op in self.config["operations"]:
                asset_results.update(self._execute_op(asset, op))
            results[asset] = asset_results

        self._persist_state(results)
        return results

    def _execute_op(self, asset, op):
        """Dispatches the operation to the relevant Cobalt tool."""
        # Mock implementations
        if op == "QUOTE": return {"Price": 150.00, "Change %": "+1.2"}
        if op == "SMC_SCAN": return {"SMC_Trend": "BULLISH"}
        return {}

    def _persist_state(self, results):
        """Saves current data for visualization."""
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        state = {
            "last_updated": datetime.now().isoformat(),
            "display_name": self.config["display_name"],
            "columns": self.config["display_columns"],
            "data": results
        }
        with open(self.state_path, 'w') as f:
            json.dump(state, f, indent=4)

```