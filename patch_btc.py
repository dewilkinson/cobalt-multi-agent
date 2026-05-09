import json
import os

CACHE_FILE = "data/brokerage_cache.json"

with open(CACHE_FILE, "r") as f:
    data = json.load(f)

account = "Rollover IRA *5513"
if account in data:
    activities = data[account].get("activities", [])
    
    # Check if already patched
    already_patched = any(act.get("id") == "MANUAL-PATCH-BTC-2026-03-28T16:00:00.000Z-150.0-SELL" for act in activities)
    
    if not already_patched:
        new_trade = {
            "id": "MANUAL-PATCH-BTC-2026-03-28T16:00:00.000Z-150.0-SELL",
            "type": "SELL",
            "units": 150.0,
            "price": 34.0,  # Estimated price
            "trade_date": "2026-03-28T16:00:00.000Z",
            "status": "Executed",
            "symbol": {
                "symbol": "BTC"
            }
        }
        activities.append(new_trade)
        
        # Sort chronologically, newest first (trade_date descending)
        activities.sort(key=lambda x: x.get('trade_date', ''), reverse=True)
        
        data[account]["activities"] = activities
        
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print("Successfully patched BTC missing trade.")
    else:
        print("Trade already patched.")
else:
    print("Account not found.")
