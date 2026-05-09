import httpx
import asyncio

async def main():
    resp = await httpx.AsyncClient().post('http://127.0.0.1:8000/api/vli/action-plan', json={'text': 'Please analyze today\'s executed trades and generate a detailed Daily Trading Report post-mortem.'}, timeout=None)
    print(resp.status_code)
    print(resp.text)

asyncio.run(main())
