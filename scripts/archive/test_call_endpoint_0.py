import asyncio
import json
import httpx
from datetime import datetime, timezone, timedelta

async def test_endpoint():
    with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json', 'r') as f:
        cache = json.load(f)
    account_id = list(cache.keys())[0]

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    start_date = start.strftime("%Y-%m-%d")
    end_date = end.strftime("%Y-%m-%d")

    url = f"http://127.0.0.1:8000/api/brokerage/history?account_id={account_id}&start_date={start_date}&end_date={end_date}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.get(url)
            print("Status Code:", r.status_code)
            data = r.json()
            if "history" in data:
                print(f"History Length: {len(data['history'])}")
                if data["history"]:
                    print(f"Sample: {data['history'][0]}")
            else:
                print("Data:", data)
        except Exception as e:
            print("Error:", e)

asyncio.run(test_endpoint())
