import os
import sys
import time
import json
import logging
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
try:
    from win10toast import ToastNotifier
except ImportError:
    ToastNotifier = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [FIDELITY_SCRAPER] - %(message)s")
logger = logging.getLogger(__name__)

# Load env
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(base_dir, "backend", ".env")
load_dotenv(env_path, override=True)

USER = os.getenv("FIDELITY_USERNAME")
PASS = os.getenv("FIDELITY_PASSWORD")

USER_DATA_DIR = os.path.join(base_dir, "data", "fidelity_session")
CACHE_FILE = os.path.join(base_dir, "data", "brokerage_cache.json")
ORDERS_URL = "https://digital.fidelity.com/ftgw/digital/portfolio/summary"

def notify_2fa():
    if ToastNotifier:
        toaster = ToastNotifier()
        toaster.show_toast("Fidelity 2FA Required", "Please authenticate in the opened browser window to resume the scraper.", duration=10)
    logger.warning("Waiting for manual 2FA / Login completion...")

def authenticate_headed_mode():
    """Launch headed browser so user can type 2FA and login."""
    notify_2fa()
    with sync_playwright() as p:
        # Launch headed to allow user interaction
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            channel="chrome", # Using native chrome avoids some bot detection
            no_viewport=True,
            args=[
                '--disable-http2',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars'
            ]
        )
        page = context.pages[0]
        page.goto(ORDERS_URL)
        
        # Wait indefinitely until we reach the orders page (login successful)
        logger.info("Browser opened. Please login and complete 2FA.")
        while "login" in page.url.lower():
            time.sleep(2)
            
        logger.info("Successfully reached Orders page. Saving session and closing headed mode.")
        context.close()

def run_polling_loop():
    with sync_playwright() as p:
        # Try headless first
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=True,
            channel="chrome",
            args=[
                '--disable-http2',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars'
            ]
        )
        page = context.pages[0]
        
        while True:
            logger.info("Polling Fidelity Orders...")
            try:
                page.goto(ORDERS_URL, wait_until="domcontentloaded")
                time.sleep(5) # Let SPA load
                
                # Check if we got redirected to login
                if "login" in page.url.lower():
                    logger.warning("Session expired or 2FA required. Escaping to Headed mode.")
                    context.close()
                    authenticate_headed_mode()
                    # Re-launch headless after auth
                    context = p.chromium.launch_persistent_context(
                        USER_DATA_DIR,
                        headless=True,
                        channel="chrome",
                        args=[
                            '--disable-http2',
                            '--disable-blink-features=AutomationControlled',
                            '--disable-infobars'
                        ]
                    )
                    page = context.pages[0]
                    continue
                    
                # We are on the orders page.
                # Dump DOM for debugging / analysis
                html_content = page.content()
                dump_path = os.path.join(base_dir, "data", "fidelity_orders_dom.html")
                with open(dump_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info(f"Saved DOM to {dump_path}. Ready to build exact parsing logic.")
                
                # TODO: Parse exact times and update BrokerageCache.
                # For now, just poll every 5 minutes.
                
            except Exception as e:
                logger.error(f"Error during polling: {e}")
                
            time.sleep(300)

if __name__ == "__main__":
    if not USER or not PASS:
        logger.error("FIDELITY_USERNAME and FIDELITY_PASSWORD must be in your .env")
        sys.exit(1)
        
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    logger.info("Starting Fidelity Background Scraper Service...")
    run_polling_loop()
