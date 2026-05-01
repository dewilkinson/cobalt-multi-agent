import asyncio
import json
import numpy as np
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def diagnostic():
    print("--- STARTING SCANNER DIAGNOSTIC V3 ---")
    
    print("\n--- INJECTING AGGRESSIVE JSON INTERCEPTOR ---")
    original_dumps = json.dumps
    
    def recursive_find_numpy(obj, path="root"):
        findings = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                findings.extend(recursive_find_numpy(v, f"{path}['{k}']"))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                findings.extend(recursive_find_numpy(v, f"{path}[{i}]"))
        elif "numpy" in str(type(obj)) or type(obj).__name__ == "int64":
            findings.append((path, type(obj).__name__, obj))
        return findings

    occurrence_log = []

    def patched_dumps(obj, *args, **kwargs):
        findings = recursive_find_numpy(obj)
        if findings:
            print("\n!!! [DETECTOR] NumPy Type found in JSON Payload !!!")
            for path, t_name, val in findings:
                print(f"  LOCATION: {path}")
                print(f"  TYPE: {t_name}")
                print(f"  VALUE: {val}")
                
            try:
                res = original_dumps(obj, *args, **kwargs)
                occurrence_log.append("SUCCESS")
                print("  => [RESULT] Serialization SUCCEEDED (Handled gracefully)")
                return res
            except Exception as serialize_error:
                occurrence_log.append("FAILED")
                print(f"  => [RESULT] INTERNAL ERROR: Serialization FAILED -> {serialize_error}")
                raise serialize_error
        return original_dumps(obj, *args, **kwargs)
        
    json.dumps = patched_dumps
    
    print("\nTesting naked json.dumps(np.int64(1))...")
    try:
        json.dumps(np.int64(1))
    except Exception as e:
        print(f"Expected failure caught: {e}")


    # 3. Import the _impl functions directly
    from src.tools.scanner import _build_session_watchlist_impl, _run_activity_pulse_impl
    
    print("\nTesting _build_session_watchlist_impl directly...")
    try:
        res_str = await _build_session_watchlist_impl(universe_csv="AAPL,TSLA")
        print("Function returned successfully.")
        data = json.loads(res_str)
        print(f"Data keys: {data.keys()}")
        # Check for any lingering numpy types in detail
        for entry in data.get("detail", []):
             for k, v in entry.items():
                 if "numpy" in str(type(v)):
                     print(f"  WARNING: Found numpy type in {k}: {type(v)}")
    except Exception as e:
        print(f"FAILED _build_session_watchlist_impl: {e}")

    # 4. Probe for other JSON libraries
    print("\nProbing for other JSON libraries...")
    for lib in ["orjson", "ujson"]:
        try:
            m = __import__(lib)
            print(f"DEBUG: {lib} is installed.")
        except ImportError:
            print(f"DEBUG: {lib} is not installed.")

    # 5. Final Pulse Test via _impl
    print("\nRunning _run_activity_pulse_impl directly...")
    try:
        res = await _run_activity_pulse_impl(watchlist=json.dumps(["AAPL"]))
        print("_run_activity_pulse_impl execution finished.")
        # Check if output is serializable
        json.dumps(json.loads(res))
        print("Final re-serialization success.")
    except Exception as e:
        print(f"FAILED _run_activity_pulse_impl: {e}")

if __name__ == "__main__":
    asyncio.run(diagnostic())
