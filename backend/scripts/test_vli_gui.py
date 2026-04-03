import os
import time
from playwright.sync_api import sync_playwright

# --- Configuration ---
VAULT_ROOT = r"C:\github\obsidian-vault"
COBALT_DIR = "_cobalt"
INBOX_DIR = "inbox"
inbox_path = os.path.join(VAULT_ROOT, COBALT_DIR, INBOX_DIR)
test_draft_file = os.path.join(inbox_path, "gui_test_draft.txt")

DASHBOARD_URL = "http://127.0.0.1:8089/VLI_session_dashboard.html"

def cleanup():
    """Remove test file if it exists."""
    if os.path.exists(test_draft_file):
        os.remove(test_draft_file)

def run_gui_test():
    print("🚀 Starting VLI Dashboard GUI Verification...")
    print("=============================================")
    cleanup()

    with sync_playwright() as p:
        # Launch browser in headed mode to visually see the test executing
        print("1. Launching Chromium Browser...")
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        # Step 1: Navigate to the Dashboard
        print(f"2. Navigating to {DASHBOARD_URL}...")
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
        try:
            page.goto(DASHBOARD_URL, timeout=10000)
        except Exception as e:
            print(f"❌ FAIL: Could not reach the dashboard. Is the HTTP server running on port 8089?\nError: {e}")
            cleanup()
            return
            
        page.wait_for_load_state('domcontentloaded')

        # Assert connection state
        conn_status = page.locator('#conn-status').inner_text()
        if conn_status != "VLI Linked":
            print(f"⚠️ Dashboard connection status check warning: Found '{conn_status}' instead of 'VLI Linked'.")

        # Step 2: Validate Vault Inbox (Before test file)
        print("3. Validating Initial Vault Inbox Monitor state...")
        inbox_pane = page.locator('#inbox-pane')
        inbox_pane.wait_for(state="visible", timeout=5000)
        
        # Step 3: Inject file and verify it appears
        print("4. Injecting test file: gui_test_draft.md...")
        os.makedirs(inbox_path, exist_ok=True)
        with open(test_draft_file, 'w') as f:
            f.write("Testing Inbox UI from Playwright!")

        print("5. Waiting for 2s polling UI update...")
        # Since polling is every 2s, wait up to 6 seconds for the span element with the file name to appear inside inbox-pane
        try:
            page.locator('#inbox-pane span', has_text="gui_test_draft.txt").wait_for(state="visible", timeout=6000)
            print("   ✅ SUCCESS: 'gui_test_draft.txt' detected organically in the VLI Dashboard!")
        except Exception as e:
            print("   ❌ FAIL: The test draft did not appear in the Vault Inbox Monitor.")
            print(f"      (Ensure the backend is running and watching the inbox: {e})")

        # Step 4: Validate Dynamic Live UI panel triggering
        print("6. Validating Live UI Wiring (Futures Watchlist)...")
        chat_input = page.locator('#chat-input')
        
        # We simulate pasting the prompt
        prompt_text = "Please create me a new watchlist window for Futures to monitor these shields."
        chat_input.fill(prompt_text)
        print(f"   - Typed prompt: '{prompt_text}'")
        
        # Instead of searching for the icon, just trigger the JS function directly to be 100% sure
        page.evaluate('sendMessage()')
        print("   - Triggered 'sendMessage()' via evaluation...")

        # Step 5: Wait for the panel
        print("7. Waiting for Dynamic Panel (watch-futures-01) to appear in the DOM...")
        try:
            # Look for the new div card
            dynamic_panel = page.locator('#watch-futures-01')
            dynamic_panel.wait_for(state="visible", timeout=15000)
            
            # Verify panel has content (the sortino indicators we added)
            title = dynamic_panel.locator('.card-header').inner_text()
            print(f"   ✅ SUCCESS: Dynamic Panel generated! Title -> '{title}'")
            
            # Optionally check that the sortino indicator is visible inside the card
            indicator = dynamic_panel.locator('.sortino-indicator')
            if indicator.count() > 0:
                print("   ✅ SUCCESS: Sortino Indicators successfully rendered inside the dynamic panel.")
            else:
                print("   ⚠️ WARNING: Dynamic panel appeared but 'sortino-indicator' CSS elements are missing.")
                
        except Exception as e:
            print("   ❌ FAIL: Dynamic Panel did not appear. (Check if the symbol extraction triggered).")
            print(e)
            
        print("8. Pausing for human verification (3s)...")
        time.sleep(3)
        
        browser.close()
        cleanup()
        print("=============================================")
        print("✨ Automated GUI Verification Complete.")

if __name__ == "__main__":
    run_gui_test()
