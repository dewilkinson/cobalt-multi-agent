import asyncio
import base64
import os
import logging
from pathlib import Path
from typing import Optional, List

from playwright.async_api import async_playwright, BrowserContext, Page

logger = logging.getLogger(__name__)

# Centralized storage for browser sessions
DEFAULT_CONTEXT_DIR = str((Path(__file__).parent.parent.parent / "data" / "playwright" / "studio_session").resolve())

class PlaywrightCapturer:
    """
    A utility to capture screenshots/framebuffers from a headless or headful browser.
    Designed for integration into CMA agents (e.g., Imaging, Studio Monitor).
    """

    def __init__(self, context_dir: str = DEFAULT_CONTEXT_DIR):
        self.context_dir = context_dir
        # Ensure directory exists
        os.makedirs(self.context_dir, exist_ok=True)

    async def capture_screenshot_headless(self, url: str, wait_seconds: int = 5) -> str:
        """
        Navigates to a URL headlessly and returns a base64 encoded PNG.
        Uses the persistent context from self.context_dir.
        """
        async with async_playwright() as p:
            logger.info(f"Launching headless browser with context: {self.context_dir}")
            try:
                # Launch persistent context with stealth args to bypass Google blocks
                context = await p.chromium.launch_persistent_context(
                    self.context_dir,
                    headless=True,
                    channel="chrome",
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                    viewport={"width": 1280, "height": 800}
                )
                
                page = context.pages[0] if context.pages else await context.new_page()
                
                logger.info(f"Navigating to {url}...")
                await page.goto(url, wait_until="networkidle", timeout=60000)
                
                # Wait for hydration/rendering
                logger.info(f"Waiting {wait_seconds}s for page hydration...")
                await asyncio.sleep(wait_seconds)
                
                # Take screenshot
                screenshot_bytes = await page.screenshot(type="png", full_page=False)
                await context.close()
                
                # Return as data URI
                b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                return f"data:image/png;base64,{b64}"
                
            except Exception as e:
                logger.error(f"Playwright capture failed: {e}")
                raise

    async def launch_headful_login(self, url: str):
        """
        Launches a headful (visible) browser for one-time user authentication.
        Blocks until the browser is manually closed.
        """
        async with async_playwright() as p:
            logger.info(f"Launching headful browser for login: {url}")
            context = await p.chromium.launch_persistent_context(
                self.context_dir,
                headless=False,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"],
                viewport={"width": 1280, "height": 800}
            )
            
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(url)
            
            print("--------------------------------------------------")
            print("🔑 BROWSER OPEN: Please log in to Google AI Studio.")
            print("🛑 CLOSE the browser window manually when finished.")
            print("--------------------------------------------------")
            
            # Keep the browser open until it's closed manually
            # We use a wait_for_event trick or just a loop
            browser_closed = asyncio.Event()
            context.on("close", lambda _: browser_closed.set())
            
            await browser_closed.wait()
            logger.info("Login browser closed by user.")
