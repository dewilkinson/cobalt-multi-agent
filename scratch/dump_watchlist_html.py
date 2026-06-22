import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            print("Navigating to http://localhost:8000/vli_dashboard.html...")
            await page.goto("http://localhost:8000/vli_dashboard.html", timeout=15000)
            print("Page loaded. Waiting for 3 seconds...")
            await asyncio.sleep(3)
            
            # Extract HTML of the watchlist table
            tbody_html = await page.evaluate('''() => {
                const tbody = document.querySelector('.macro-watchlist-body-instance');
                return tbody ? tbody.innerHTML : "Not found";
            }''')
            
            output_path = os.path.join(os.path.dirname(__file__), 'tbody.html')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(tbody_html)
            print("HTML saved to scratch/tbody.html successfully.")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
