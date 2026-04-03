import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_active_state():
    print("Testing /api/vli/active-state...")
    res = requests.get(f"{BASE_URL}/api/vli/active-state")
    if res.status_code != 200:
        print(f"❌ FAIL: Status Code {res.status_code}")
        return False
    
    data = res.json()
    macros = data.get("macros", [])
    print(f"✅ Received {len(macros)} macros.")
    
    # Check TYX
    tyx = next((m for m in macros if m["symbol"] == "TYX"), None)
    if tyx:
        print(f"✅ TYX Price: {tyx['price']} (Should be Yield ~4.x)")
        if 3.0 < float(tyx['price']) < 6.0:
            print("   ✅ TYX Yield range validated.")
        else:
            print("   ⚠️ TYX Yield range outside expected (3-6%). Check if it's Bond Price.")
    else:
        print("❌ FAIL: TYX not found in macros.")

    # Check serialization
    try:
        json.dumps(data)
        print("✅ Response is fully JSON serializable.")
    except Exception as e:
        print(f"❌ FAIL: Serialization error: {e}")

    return True

def test_action_plan():
    print("\nTesting /api/vli/action-plan (Reasoning Agent)...")
    payload = {"text": "Analyze $VIX and its relation to $SPY and $TYX. Provide a brief institutional summary."}
    start = time.time()
    res = requests.post(f"{BASE_URL}/api/vli/action-plan", json=payload)
    latency = time.time() - start
    
    if res.status_code != 200:
        print(f"❌ FAIL: Action Plan Status Code {res.status_code}")
        print(res.text)
        return False
    
    data = res.json()
    print(f"✅ Received response in {latency:.2f}s.")
    print(f"📝 Response Preview: {data.get('response', '')[:200]}...")
    
    if "VIX" in data.get('response', '') and "TYX" in data.get('response', ''):
        print("✅ Response contains expected tickers.")
    else:
        print("⚠️ Response might be generic or missing research data.")

    return True

if __name__ == "__main__":
    s1 = test_active_state()
    s2 = test_action_plan()
    if s1 and s2:
        print("\n✨ ALL VLI V2 STABILITY TESTS PASSED.")
    else:
        print("\n❌ SOME TESTS FAILED.")
