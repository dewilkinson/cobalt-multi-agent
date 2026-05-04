import asyncio, json, sys, os
sys.path.append(os.path.abspath('c:\\github\\cobalt-multi-agent\\backend'))
from src.server.routes.scanner import scanner_stream

async def test():
    resp = await scanner_stream()
    async for chunk in resp.body_iterator:
        print(chunk)
asyncio.run(test())
