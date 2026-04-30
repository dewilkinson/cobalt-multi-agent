import time
import requests

URL = 'http://127.0.0.1:8000/api/vli/action-plan'
HEADERS = {'Content-Type': 'application/json'}

def fetch_kie():
    t0 = time.time()
    requests.post(URL, headers=HEADERS, json={'text': '$KIE', 'raw_data_mode': True, 'direct_mode': False, 'is_action_plan': False})
    return time.time() - t0

# Since this script runs outside the server process, the server retains cache memory between these two calls.
# We assume KIE is not in the server cache right now. If it is, the first call might be fast.
print("Fetching KIE (Initial/Cache Miss)...")
t1 = fetch_kie()
print(f"Time 1: {t1:.3f} seconds")

print("\nFetching KIE Again (Cache Hit expected)...")
t2 = fetch_kie()
print(f"Time 2: {t2:.3f} seconds")

print(f"\nSpeedup: {t1/t2:.1f}x ({(t1-t2):.3f}s saved)")
