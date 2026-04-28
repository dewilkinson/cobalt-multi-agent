import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("POST", "http://localhost:8000/api/vli/action-plan", json={
                "text": "analyze NVDA"
            }, timeout=120.0) as resp:
                async for line in resp.aiter_lines():
                    print(line)
        except Exception as e:
            print("Error:", e)

asyncio.run(test())
