import asyncio
from src.server.app import get_brokerage_history

async def test():
    res = await get_brokerage_history('__POSITIONS__', '2026-04-30', '2026-04-30')
    print(res.body.decode())

asyncio.run(test())
