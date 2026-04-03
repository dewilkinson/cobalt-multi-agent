import asyncio
import json
import logging
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from src.server.app import _invoke_vli_agent
from src.tools.finance import history_cache

logging.basicConfig(level=logging.INFO)

async def test_reproduction():
    print("--- STEP 1: Initial Macro Fetch (Expected: Fast-Path) ---")
    res1 = await _invoke_vli_agent("get macro symbol price")
    print(f"Result 1:\n{res1}")

    print("\n--- STEP 2: Fresh Macro Fetch (Expected: Full Graph Execution) ---")
    # This should now skip the fast-track due to 'fresh' keyword
    res2 = await _invoke_vli_agent("get fresh macro symbol price")
    print(f"Result 2:\n{res2}")

    print("\n--- STEP 3: Invalidate Cache and Macro (Expected: Full Graph Execution) ---")
    res3 = await _invoke_vli_agent("invalidate cache and get macro symbol price")
    print(f"Result 3:\n{res3}")

if __name__ == "__main__":
    asyncio.run(test_reproduction())
