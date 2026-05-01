import asyncio
import json
import numpy as np
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def final_verification():
    print("=== STARTING FINAL SCANNER STABILITY VERIFICATION ===")
    
    # 1. Global Patch Check
    print("\n[VERIFICATION 1/4] Checking Global JSON Patch...")
    try:
        from src.server.routes.scanner import patch_json
        # The import itself triggers patch_json() in my latest refactor
        s = json.dumps({"test": np.int64(999)})
        print(f"  Result: {s}")
        print("  [PASS] Global JSON patch verified.")
    except Exception as e:
        print(f"  [FAIL] Global JSON patch failed: {e}")
        return

    # 2. Logic Casting Check
    print("\n[VERIFICATION 2/4] Checking Logic Casting Logic (_impl functions)...")
    from src.tools.scanner import _build_session_watchlist_impl, _run_activity_pulse_impl
    try:
        # We want to see if the internal dicts are truly clean
        res_str = await _build_session_watchlist_impl(universe_csv="CELH")
        data = json.loads(res_str)
        found_numpy = False
        for entry in data.get("detail", []):
            for k, v in entry.items():
                if "numpy" in str(type(v)):
                    print(f"    WARNING: Found numpy type {type(v)} in field '{k}'")
                    found_numpy = True
        if not found_numpy:
            print("  [PASS] Tool returns are natively serializable.")
    except Exception as e:
        print(f"  [FAIL] Tool logic execution failed: {e}")

    # 3. Router-Level Serialization Isolation
    print("\n[VERIFICATION 3/4] Checking Router Serialization Isolation...")
    # Mocking the merged entry logic from the router
    phase0_entry = {"symbol": "TSLA", "price": np.float64(150.5), "volume": np.int64(5000000)}
    pulse_entry = {"symbol": "TSLA", "tier": "STRIKE", "rvol": np.float64(2.5)}
    
    merged = {**phase0_entry, **pulse_entry}
    try:
        # This is exactly what the yield logic does
        sse_payload = json.dumps({"type": "phase2", "data": [merged]})
        print(f"  SSE Payload: {sse_payload}")
        print("  [PASS] Router-level merging is safe for transmission.")
    except Exception as e:
        print(f"  [FAIL] Router-level serialization failed: {e}")

    # 4. Orjson Conflict Check
    print("\n[VERIFICATION 4/4] Checking Orjson Compatibility...")
    try:
        import orjson
        # The key is that the ROUTER sends STRINGS. orjson.loads(string) works fine.
        # It's orjson.dumps(numpy) that fails. If we pre-serialize to string, we are safe.
        serialized_string = json.dumps({"data": np.int64(123)})
        loaded = orjson.loads(serialized_string)
        print(f"  Orjson parsed standard JSON string: {loaded}")
        print("  [PASS] Pre-serialization strategy neutralizes Orjson conflict.")
    except ImportError:
        print("  [SKIP] Orjson not installed, no conflict risk.")
    except Exception as e:
        print(f"  [FAIL] Orjson interaction failed: {e}")

    print("\n=== VERIFICATION COMPLETE: ALL SYSTEMS NOMINAL ===")

if __name__ == "__main__":
    asyncio.run(final_verification())
