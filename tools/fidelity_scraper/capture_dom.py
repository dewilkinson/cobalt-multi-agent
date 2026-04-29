import os
import sys
import time
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [DOM_CAPTURE] - %(message)s")
logger = logging.getLogger(__name__)

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USER_DATA_DIR = os.path.join(base_dir, "data", "fidelity_session")
START_URL = "https://digital.fidelity.com/ftgw/digital/portfolio/summary"

def capture():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            channel="chrome",
            no_viewport=True,
            args=[
                '--window-position=0,0',
                '--disable-http2',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars'
            ]
        )
        page = context.pages[0]
        page.goto(START_URL)
        
        logger.info("Browser opened! Please login and complete 2FA.")
        logger.info("After logging in, manually navigate to the 'Activity & Orders' tab.")
        
        logger.info("Setting up network interception for raw JSON data...")
        
        def handle_response(response):
            try:
                url = response.url.lower()
                ct = response.headers.get("content-type", "").lower()
                with open("data/fidelity_urls.txt", "a", encoding="utf-8") as f:
                    f.write(f"{ct} | {url}\n")
            except:
                pass
                
        page.on("response", handle_response)
        
        input("\n>>> PRESS ENTER HERE IN THE TERMINAL ONCE THE ORDERS ARE VISIBLE ON SCREEN <<<\n")
        
        logger.info("Successfully recorded all URLs. Shutting down cleanly to save session...")
        context.close()
        sys.exit(0)

if __name__ == "__main__":
    capture()
