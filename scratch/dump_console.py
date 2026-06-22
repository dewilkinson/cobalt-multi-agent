import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Listen for console logs
        page.on("console", lambda msg: print(f"CONSOLE: {msg.type} - {msg.text}"))
        page.on("pageerror", lambda err: print(f"PAGE_ERROR - {err}"))
        
        try:
            print("Navigating to http://localhost:8000/vli_dashboard.html...")
            await page.goto("http://localhost:8000/vli_dashboard.html", timeout=15000)
            print("Page loaded. Waiting for 3 seconds...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"Navigation or wait error: {e}")
        finally:
            await browser.close()
            print("Browser closed.")

if __name__ == "__main__":
    asyncio.run(main())
