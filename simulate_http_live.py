import subprocess
import time
from playwright.sync_api import sync_playwright
import os

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    print("Page loaded (server is offline).")
    page.goto("http://localhost:8000/vli_dashboard.html")
    # Wait, if server is offline, http://localhost:8000 will FAIL TO LOAD!
    # Let's use python's http.server to serve the static file on port 5500 to simulate the user's environment!
