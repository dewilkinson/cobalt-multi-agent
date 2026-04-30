import time
from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            "data/fidelity_session",
            headless=False,
            channel="chrome",
            args=[
                '--window-position=-32000,-32000',
                '--disable-http2',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars'
            ]
        )
        page = context.pages[0]
        page.goto("https://digital.fidelity.com/ftgw/digital/portfolio/summary", wait_until="domcontentloaded", timeout=15000)
        time.sleep(5)
        print("Headed Success! URL:", page.url)
        context.close()
        
try:
    run()
except Exception as e:
    print("Failed:", e)
