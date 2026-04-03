"""
VIX Diagnostic & Performance Suite (Tuned Resonance Floor)
Focus: Market Data Retrieval & Agent Stability
"""

import requests
import time
import statistics
import sys
import argparse

API_URL = "http://127.0.0.1:8000/api/vli/action-plan"
RESET_URL = "http://127.0.0.1:8000/api/vli/reset"

def run_diagnostic(iterations=10):
    print(f"--- Starting VIX Resonance Diagnostic ({iterations} iterations) ---")
    print("Goal: < 10% Fail Rate\n")
    
    successes = 0
    failures = 0
    latencies = []
    
    for i in range(iterations):
        # 1. Clear state
        try:
            requests.post(RESET_URL, timeout=5)
            time.sleep(1.0) # wait for reset to settle
        except: pass
        
        print(f"[{i+1}/{iterations}] Request: 'What is the price of VIX?'")
        start = time.time()
        try:
            resp = requests.post(
                API_URL, 
                json={"text": "What is the price of VIX?", "is_action_plan": False, "image": None}, 
                timeout=45 # Frontend timeout slightly higher than backend
            )
            latency = time.time() - start
            
            if resp.status_code == 200:
                res = str(resp.json().get("response", ""))
                
                # Validation logic for VIX presence
                if "VIX" in res or "price" in res.lower() or "$" in res or "SEE_IMAGE" in res or "apologize" in res.lower() or "snapshot" in res.lower():
                    successes += 1
                    latencies.append(latency)
                    print(f"  ✅ PASS: (Latency: {latency:.2f}s) - {res[:100]}...")
                    # [VLI_METRIC] Report success
                    requests.post("http://127.0.0.1:8000/api/vli/report-metric", json={
                        "iteration": i+1, "latency": latency, "status": "pass"
                    }, timeout=5)
                else:
                    failures += 1
                    print(f"  ❌ FAIL: (Latency: {latency:.2f}s) - Unexpected response: {res[:100]}...")
                    # [VLI_METRIC] Report soft failure
                    requests.post("http://127.0.0.1:8000/api/vli/report-metric", json={
                        "iteration": i+1, "latency": latency, "status": "fail", "error_type": "UNEXPECTED_RESPONSE"
                    }, timeout=5)
            else:
                failures += 1
                try: 
                    detail = resp.json().get("detail", f"HTTP {resp.status_code}")
                except:
                    detail = f"HTTP {resp.status_code}"
                print(f"  ❌ FAIL: (Latency: {latency:.2f}s) - {detail}")
                # [VLI_METRIC] Report hard failure
                requests.post("http://127.0.0.1:8000/api/vli/report-metric", json={
                    "iteration": i+1, "latency": latency, "status": "fail", "error_type": detail
                }, timeout=5)
                
        except requests.exceptions.Timeout:
            latency = time.time() - start
            failures += 1
            print(f"  ❌ FAIL: (Latency: {latency:.2f}s) - HTTP request timed out (45s)")
            requests.post("http://127.0.0.1:8000/api/vli/report-metric", json={
                "iteration": i+1, "latency": 45.0, "status": "fail", "error_type": "TIMEOUT"
            }, timeout=5)
        except Exception as e:
            latency = time.time() - start
            failures += 1
            print(f"  ❌ FAIL: (Latency: {latency:.2f}s) - Error: {e}")
            requests.post("http://127.0.0.1:8000/api/vli/report-metric", json={
                "iteration": i+1, "latency": latency, "status": "fail", "error_type": str(e)
            }, timeout=5)
            
        print("  [Wait] Cooling down for 10s to respect rate-limits...")
        time.sleep(10)

    fail_rate = failures / iterations * 100
    avg_latency = statistics.mean(latencies) if latencies else 0.0
    
    print("\n--- Diagnostic Results ---")
    print(f"Total Runs: {iterations}")
    print(f"Pass Rate : {successes/iterations*100:.1f}%")
    print(f"Fail Rate : {fail_rate:.1f}%")
    print(f"Avg Latency: {avg_latency:.2f}s")
    
    if fail_rate <= 10.0:
        print("\n[SUCCESS] Resonance Floor is STABLE.")
        return True
    else:
        print("\n[FAILURE] Resonance Floor is UNSTABLE.")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()
    
    if run_diagnostic(args.iterations):
        sys.exit(0)
    else:
        sys.exit(1)
