import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "src"))

# Mocking parts of app.py to test the logic isolation
from src.server import app

logging.basicConfig(level=logging.INFO)

async def test_logic():
    print("--- Testing Fast-Path Cooldown Logic ---")
    
    # 1. Reset timer
    app._vli_fast_path_cooldown_until = datetime.now() - timedelta(seconds=1)
    
    # 2. Test standard query (Should be fast track if it matches)
    # We will look at the internal logic of _invoke_vli_agent locally or simulate it
    text_standard = "get macro symbol price"
    # Manual check of the logic we just added to app.py
    
    is_macro = "MACRO" in text_standard.upper() and ("LIST" in text_standard.upper() or "PRICE" in text_standard.upper())
    refresh_keywords = ["REFRESH", "FRESH", "LATEST", "INVALIDATE", "CLEAR", "RE-SCROLL"]
    is_refresh_requested = any(kw in text_standard.upper() for kw in refresh_keywords)
    is_cooldown_active = datetime.now() < app._vli_fast_path_cooldown_until
    
    print(f"Standard: is_macro={is_macro}, is_refresh={is_refresh_requested}, is_cooldown={is_cooldown_active}")
    is_fast_track = is_macro and not is_refresh_requested and not is_cooldown_active
    print(f"Result (Standard): is_fast_track={is_fast_track} (Expected: True)")

    # 3. Test Invalidate trigger
    text_invalidate = "invalidate cache"
    if any(kw in text_invalidate.upper() for kw in ["INVALIDATE", "CLEAR"]):
        app._vli_fast_path_cooldown_until = datetime.now() + timedelta(minutes=5)
    
    is_cooldown_active_post = datetime.now() < app._vli_fast_path_cooldown_until
    print(f"After 'invalidate': is_cooldown={is_cooldown_active_post} (Expected: True)")

    # 4. Test subsequent query during cooldown
    text_retry = "get macro symbol price"
    is_macro_retry = "MACRO" in text_retry.upper() and ("LIST" in text_retry.upper() or "PRICE" in text_retry.upper())
    is_refresh_retry = any(kw in text_retry.upper() for kw in refresh_keywords)
    is_cooldown_retry = datetime.now() < app._vli_fast_path_cooldown_until
    
    is_fast_track_retry = is_macro_retry and not is_refresh_retry and not is_cooldown_retry
    print(f"Retry during cooldown: is_fast_track={is_fast_track_retry} (Expected: False)")

if __name__ == "__main__":
    asyncio.run(test_logic())
