import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.services.asset_bucket import AssetBucket

async def test_macro():
    monitor = AssetBucket("MACRO_WATCHLIST", display_name="Macros", vault_path="C:/github/obsidian-vault")
    print(f"Bucket Loaded: {monitor.config['display_name']}")
    print(f"Operations: {monitor.config['operations']}")
    print(f"Priority: {monitor.config.get('priority')}")
    
    # First update
    print("\n--- FIRST UPDATE ---")
    res1 = await monitor.update()
    for k, v in res1.items():
        print(f"{k}: {v}")
        
    # Second update immediately (should skip FETCH_OCHL and CALC_REGIME, only do FETCH_PRICE)
    print("\n--- SECOND UPDATE (IMMEDIATE) ---")
    res2 = await monitor.update()
    for k, v in res2.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    asyncio.run(test_macro())

