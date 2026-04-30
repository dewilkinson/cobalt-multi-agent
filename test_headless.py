import time
from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            "data/fidelity_session",
            headless=True,
            channel="chrome",
            args=[
                '--disable-http2',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars'
            ]
        )
        page = context.pages[0]
        page.goto("https://digital.fidelity.com/ftgw/digital/portfolio/summary")
        time.sleep(5)
        print("URL:", page.url)
        context.close()
        
run()
