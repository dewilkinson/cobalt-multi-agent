import os
import time
import statistics
import sys
from playwright.sync_api import sync_playwright

# --- Configuration ---
DASHBOARD_URL = "http://127.0.0.1:8089/VLI_session_dashboard.html"
ITERATIONS = 10
TICKER = "VIX"

def run_resonance_test():
    print(f"🚀 Starting VIX Dashboard Resonance Test ({ITERATIONS} iterations)...")
    print("=============================================")

    with sync_playwright() as p:
        print("1. Launching Chromium Browser...")
        browser = p.chromium.launch(headless=False, slow_mo=200)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        # Step 1: Navigate to the Dashboard
        print(f"2. Navigating to {DASHBOARD_URL}...")
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
        try:
            page.goto(DASHBOARD_URL, timeout=15000)
        except Exception as e:
            print(f"❌ FAIL: Could not reach the dashboard. Is the HTTP server running?\nError: {e}")
            return
            
        page.wait_for_load_state('networkidle')
        
        successes = 0
        latencies = []
        
        chat_input = page.locator('#chat-input')
        
        for i in range(ITERATIONS):
            print(f"[{i+1}/{ITERATIONS}] Iteration: 'What is the price of {TICKER}?'")
            
            # Record start time
            start_time = time.time()
            
            # Clear and fill input
            chat_input.fill(f"What is the price of {TICKER}?")
            
            # Trigger send via keyboard (Command/Ctrl + Enter) or clicking the button
            # We'll use the sendMessage() evaluation for consistency with existing tests
            page.evaluate('sendMessage()')
            
            # Wait for the AI message to appear or update
            # The dashboard adds an 'ai-message' with an ID 'ai-loading-indicator' during thinking
            # and replaces it with the final result.
            
            try:
                # Wait for the loading indicator to disappear (or the final message to contain data)
                # We expect the last .ai-message to NOT contain "Thinking..."
                page.wait_for_function(
                    """() => {
                        const msgs = document.querySelectorAll('.ai-message');
                        if (msgs.length === 0) return false;
                        const last = msgs[msgs.length - 1];
                        return !last.innerText.includes('Thinking...') && 
                               (last.innerText.includes('$') || 
                                last.innerText.includes('price') || 
                                last.innerText.includes('VIX'));
                    }""",
                    timeout=40000 # 40s timeout for agent fallback
                )
                
                latency = time.time() - start_time
                successes += 1
                latencies.append(latency)
                
                # Get the response text for logging
                response_text = page.locator('.ai-message').last.inner_text()
                print(f"  ✅ PASS: (Latency: {latency:.2f}s) - {response_text[:80]}...")
                
            except Exception as e:
                latency = time.time() - start_time
                print(f"  ❌ FAIL: (Latency: {latency:.2f}s) - Response timed out or unexpected.")
                # print(f"      Debug Error: {e}")

            # Check if UI is "blocked" - try to type something into the input
            try:
                chat_input.fill("Still alive?")
                # If fill doesn't throw, the UI is likely not completely frozen
            except Exception as e:
                print(f"  🚨 CRITICAL: UI is BLOCKED! Cannot interact with input. {e}")
                break

            # Short cooldown
            time.sleep(2)
            
        # Final Summary
        avg_latency = statistics.mean(latencies) if latencies else 0.0
        print("\n" + "="*30)
        print(f"Test Complete: {successes}/{ITERATIONS} Successes")
        if latencies:
            print(f"Avg UI-to-AI Latency: {avg_latency:.2f}s")
        print("="*30)
        
        time.sleep(3)
        browser.close()

if __name__ == "__main__":
    run_resonance_test()
