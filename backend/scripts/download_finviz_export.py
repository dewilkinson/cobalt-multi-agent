import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Add backend to path if needed
sys.path.append(str(Path(__file__).parent.parent))

async def download_export():
    async with async_playwright() as p:
        # Launch browser. Note: we might need a persistent context if session depends on it.
        # But for now, we'll try to navigate and see if we have the session.
        browser = await p.chromium.launch(headless=True)
        # Try to use a context that might inherit session (if using a system profile)
        # Note: In some environments, Playwright can use the default Chrome profile.
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # Finviz elite URL
            url = "https://elite.finviz.com/screener?v=111&f=cap_small,sh_float_u100,sh_price_10to50,ta_perf_13w20o"
            print(f"Navigating to {url}...")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Check for login prompt
            if await page.query_selector("input[name='email']"):
                print("Error: Not logged in. Elite subscription required.")
                return False
                
            # Handle download
            async with page.expect_download() as download_info:
                print("Clicking export button...")
                # The export link usually matches a.tab-link[href^='/export.ashx']
                await page.click("a.tab-link[href*='export.ashx']")
            
            download = await download_info.value
            export_path = Path(__file__).parent.parent / "data" / "finviz_export.csv"
            os.makedirs(export_path.parent, exist_ok=True)
            
            await download.save_as(str(export_path))
            print(f"Export saved to {export_path}")
            return True
            
        except Exception as e:
            print(f"Download failed: {e}")
            # Take screenshot for debugging if it fails in a real terminal run? 
            # (Can't easily see it here)
            return False
        finally:
            await browser.close()

if __name__ == "__main__":
    success = asyncio.run(download_export())
    sys.exit(0 if success else 1)
