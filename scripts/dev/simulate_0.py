import subprocess
import time
from playwright.sync_api import sync_playwright
import os
import signal

print("Starting server...")
proc = subprocess.Popen(["python", "backend/server.py", "--port", "8000"])
time.sleep(8) # Wait for server to start

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:8000/vli_dashboard.html")
    print("Page loaded.")
    time.sleep(5)
    
    print("Killing server...")
    if os.name == 'nt':
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)])
    else:
        proc.kill()
    
    print("Waiting for SERVER OFFLINE dialog (should take ~60s)...")
    try:
        page.wait_for_selector("text='SERVER OFFLINE'", timeout=70000)
        print("SERVER OFFLINE dialog appeared!")
    except Exception as e:
        print("Failed to find dialog:", e)
    
    print("Clicking Retry...")
    page.click("button:has-text('Retry')")
    
    print("Restarting server...")
    proc2 = subprocess.Popen(["python", "backend/server.py", "--port", "8000"])
    
    print("Waiting to see what happens...")
    # Wait to see if it connects or fails again
    try:
        page.wait_for_selector("text='Connected!'", timeout=30000)
        print("SUCCESS! Reconnected.")
    except:
        print("Did not see 'Connected!'")

    try:
        page.wait_for_selector("text='SERVER OFFLINE'", timeout=65000)
        print("FAILURE! Saw second 'SERVER OFFLINE' dialog.")
    except:
        print("Did not see second 'SERVER OFFLINE'.")
        
    browser.close()
    
    print("Cleaning up...")
    if os.name == 'nt':
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc2.pid)])
    else:
        proc2.kill()
