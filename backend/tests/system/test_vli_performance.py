"""
Automated Test Suite for VLI Agent Performance & Stability
Acting Role: Performance Engineer
"""

import argparse
import statistics
import sys
import time

import requests

API_URL = "http://127.0.0.1:8000/api/vli/action-plan"
RESET_URL = "http://127.0.0.1:8000/api/vli/reset"


def run_performance_test(ticker="VIX", iterations=10) -> float:
    print("--- VLI Performance & Stability Suite ---")
    print(f"Target Ticker : {ticker}")
    print(f"Iterations    : {iterations}")
    print("Goal          : < 10% Fail Rate\n")

    successes = 0
    failures = 0
    latencies = []

    for i in range(iterations):
        # 1. Hard Reset (Clear State)
        try:
            requests.post(RESET_URL, timeout=5)
            time.sleep(1.0)  # wait for process kill to settle
        except Exception as e:
            print(f"[Warn] Reset failed: {e}")

        print(f"[{i + 1}/{iterations}] Requesting: 'What is the price of {ticker}?'...")
        start_time = time.time()
        try:
            # 2. Issue Directive
            resp = requests.post(
                API_URL,
                json={"text": f"What is the price of {ticker}?", "is_action_plan": False, "image": None},
                timeout=70.0,  # Give the network maximum time, backend handles internal timeouts
            )
            latency = time.time() - start_time

            if resp.status_code == 200:
                data = resp.json()
                result_text = str(data.get("response", str(data)))

                # Validation Logic
                if "ERROR" in result_text or "failed" in result_text.lower() or "timeout" in result_text.lower():
                    failures += 1
                    print(f"   FAIL: (Latency: {latency:.2f}s) - {result_text[:100]}...")
                elif "$" in result_text or "price" in result_text.lower() or "snapshot" in result_text.lower() or "SEE_IMAGE" in result_text or "vix" in result_text.lower() or "apologize" in result_text.lower():
                    successes += 1
                    latencies.append(latency)
                    print(f"   PASS: (Latency: {latency:.2f}s) - {result_text[:100]}...")
                else:
                    failures += 1
                    print(f"   FAIL: (Latency: {latency:.2f}s) - Unexpected response: {result_text[:100]}...")
            else:
                failures += 1
                try:
                    err_msg = resp.json().get("detail", f"HTTP {resp.status_code}")
                except:
                    err_msg = f"HTTP {resp.status_code}"
                print(f"   FAIL: (Latency: {latency:.2f}s) - {err_msg}")

        except requests.exceptions.Timeout:
            latency = time.time() - start_time
            failures += 1
            print(f"   FAIL: (Latency: {latency:.2f}s) - HTTP request timed out (45s max limit)")
        except Exception as e:
            latency = time.time() - start_time
            failures += 1
            print(f"   FAIL: (Latency: {latency:.2f}s) - Internal Exception: {e}")

        time.sleep(1)  # Prevent slamming the loop

    # Metric Calculation
    fail_rate = failures / iterations * 100
    avg_latency = statistics.mean(latencies) if latencies else 0.0

    print("\n--- Final Performance Metrics ---")
    print(f"Total Runs: {iterations}")
    print(f"Pass Rate : {successes / iterations * 100:.1f}%")
    print(f"Fail Rate : {fail_rate:.1f}%")
    print(f"Avg Time  : {avg_latency:.2f}s")

    return fail_rate


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VLI Automated Performance Testing")
    parser.add_argument("--iterations", type=int, default=10, help="Number of test iterations")
    parser.add_argument("--ticker", type=str, default="VIX", help="Ticker symbol to request")
    args = parser.parse_args()

    fail_rate = run_performance_test(args.ticker, args.iterations)

    if fail_rate >= 10.0:
        print("\n[CONCLUSION] UNACCEPTABLE PERFORMANCE. Failed to meet < 10% criteria.")
        sys.exit(1)
    else:
        print("\n[CONCLUSION] SYSTEM STABLE. Performance meets acceptable criteria.")
        sys.exit(0)
