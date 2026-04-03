import sys
from playwright.sync_api import sync_playwright

DASHBOARD_URL = "http://127.0.0.1:8089/minimal_chat.html"

def run_chat_test():
    print("🚀 Starting Minimal VLI Chat Automation GUI Test...")
    print("=============================================")

    with sync_playwright() as p:
        print("1. Launching Chromium Browser...")
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context()
        page = context.new_page()

        print(f"2. Navigating to Minimal Client ({DASHBOARD_URL})...")
        try:
            page.goto(DASHBOARD_URL, timeout=10000)
        except Exception as e:
            print(f"❌ FAIL: Could not reach the minimal chat app. Is HTTP server on port 8089 running?\nError: {e}")
            sys.exit(1)
            
        page.wait_for_load_state('domcontentloaded')

        print("3. Submitting simple test message...")
        chat_input = page.locator('#chat-input')
        
        test_message = "Hello Gemini, are you receiving my test signal?"
        chat_input.fill(test_message)
        print(f"   - Typed prompt: '{test_message}'")
        
        send_button = page.locator('#send-btn')
        send_button.click()
        print("   - Clicked Send button.")

        print("4. Waiting for AI response...")
        try:
            # We wait for the new AI message to appear.
            ai_messages = page.locator('.ai-message')
            
            # Wait for at least 1 AI message
            page.wait_for_function(
                "document.querySelectorAll('.ai-message').length > 0",
                timeout=15000
            )

            latest_response = ai_messages.last.inner_text()
            
            if "Error:" in latest_response:
                print(f"   ❌ FAIL: Received Error Response: '{latest_response}'")
            else:
                print(f"   ✅ SUCCESS: Received AI Response: '{latest_response}'")
                print("   ✅ SUCCESS: Connection made and test passed.")
            
        except Exception as e:
            print("   ❌ FAIL: Did not receive AI Response in the DOM.")
            print(f"      (Ensure the backend API at localhost:8000 is active: {e})")
            
        import time
        print("5. Pausing for human verification (3s)...")
        time.sleep(3)
        
        browser.close()
        print("=============================================")
        print("✨ Automated Minimal Chat Verification Complete.")

if __name__ == "__main__":
    run_chat_test()
