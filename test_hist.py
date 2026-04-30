import asyncio
import sys
sys.path.append('backend')
from src.server.app import get_brokerage_history

async def run():
    res = await get_brokerage_history("Health Savings Account *6937", "2026-04-29", "2026-04-29")
    import json
    print(res.body.decode('utf-8'))

asyncio.run(run())
