import os
import time
from playwright.sync_api import sync_playwright

DEBUG_URL = "http://127.0.0.1:8089/vli_debug.html"

def run_debug_test():
    print("🚀 Starting VLI Isolated Debug Verification...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        context = browser.new_context()
        page = context.new_page()

        # Step 1: Navigate to the Debug Dashboard
        print(f"2. Navigating to {DEBUG_URL}...")
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
        
        try:
            page.goto(DEBUG_URL, timeout=10000)
        except Exception as e:
            print(f"❌ FAIL: Could not reach the debug page. Is HTTP server on 8089 running?\nError: {e}")
            return
            
        page.wait_for_load_state('domcontentloaded')

        print("3. Validating Communication with 127.0.0.1:8001...")
        
        # Click the send button (it triggers the JS function)
        print("   - Clicking Send...")
        page.click("button >> text=Send")
        
        # Wait for log div to update with either success or fail message
        print("   - Waiting for fetch resolution log (up to 15s)...")
        try:
            # We look for the literal string "HTTP Status" to appear inside the log box
            page.locator('#cycleLog', has_text="HTTP Status: 200").wait_for(state="visible", timeout=15000)
            print("   ✅ SUCCESS: Fetch successfully reached the Backend on Port 8001!")
            
            # Print the entire log sequence for human verification
            logs = page.locator('#cycleLog').inner_text()
            print("\n----- CYCLE LOGS -----")
            print(logs)
            print("----------------------\n")
            
        except Exception as e:
            print("   ❌ FAIL: Fetch failed or timed out. Check if port 8001 server is running.")
            print(e)
            
        time.sleep(2)
        browser.close()
        
if __name__ == "__main__":
    run_debug_test()
