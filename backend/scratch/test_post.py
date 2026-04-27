import httpx
import asyncio

async def test():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post('http://localhost:8000/api/vli/action-plan', json={'text': 'update ARM'}, timeout=60.0)
            print("Response:", r.text)
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    asyncio.run(test())
