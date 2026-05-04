import os, asyncio, aiohttp
from dotenv import load_dotenv

load_dotenv("backend/.env")

async def main():
    api_key=os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
    url=f"https://www.alphavantage.co/query?function=TOP_GAINERS_LOSERS&apikey={api_key}&entitlement=realtime"
    print(f"Fetching from {url[:70]}...")
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            print(await resp.text())

asyncio.run(main())
