import asyncio, json, sys, os
sys.path.append(os.path.abspath('C:\\Users\\rende\\.gemini\\antigravity\\worktrees\\cobalt-multi-agent\\backend'))
from src.server.routes.scanner import scanner_stream

async def test():
    resp = await scanner_stream()
    async for chunk in resp.body_iterator:
        print(chunk)
asyncio.run(test())
