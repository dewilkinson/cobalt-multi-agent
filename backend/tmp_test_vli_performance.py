import requests
import time
import json
import statistics

API_URL = "http://127.0.0.1:8000/api/vli/action-plan"
RESET_URL = "http://127.0.0.1:8000/api/vli/reset"
TICKER = "VIX"

def run_test(iterations=10):
    print(f"--- VLI Performance & Stability Test ({iterations} iterations) ---")
    print(f"Request: 'What is the price of {TICKER}?'\n")
    
    successes = 0
    failures = 0
    latencies = []
    
    for i in range(iterations):
        # Reset state before each run to ensure independence
        try:
            requests.post(RESET_URL, timeout=5)
        except Exception as e:
            print(f"Reset failed: {e}")
            
        print(f"Iteration {i+1}...")
        start_time = time.time()
        try:
            resp = requests.post(
                API_URL, 
                json={"text": f"What is the price of {TICKER}?", "is_action_plan": False, "image": None}, 
                timeout=15
            )
            latency = time.time() - start_time
            if resp.status_code == 200:
                data = resp.json()
                result_text = data.get("response", str(data))
                if "ERROR" in result_text or "failed" in result_text.lower() or "timeout" in result_text.lower():
                    failures += 1
                    print(f"  ❌ FAIL: (Latency: {latency:.2f}s) - Error: {result_text[:100]}")
                else:
                    successes += 1
                    latencies.append(latency)
                    print(f"  ✅ PASS: (Latency: {latency:.2f}s) - {result_text[:100]}")
            else:
                failures += 1
                print(f"  ❌ FAIL: (Latency: {latency:.2f}s) - HTTP {resp.status_code}")
        except requests.exceptions.Timeout:
            latency = time.time() - start_time
            failures += 1
            print(f"  ❌ FAIL: (Latency: {latency:.2f}s) - HTTP request timed out")
        except Exception as e:
            latency = time.time() - start_time
            failures += 1
            print(f"  ❌ FAIL: (Latency: {latency:.2f}s) - Request exception: {e}")
            
        time.sleep(1)

    fail_rate = failures / iterations * 100
    avg_latency = statistics.mean(latencies) if latencies else 0.0
    
    print("\n--- Summary ---")
    print(f"Total Runs: {iterations}")
    print(f"Pass Rate : {successes/iterations*100:.1f}%")
    print(f"Fail Rate : {fail_rate:.1f}%")
    print(f"Avg Time  : {avg_latency:.2f}s")
    
    return fail_rate

if __name__ == "__main__":
    run_test(5)
