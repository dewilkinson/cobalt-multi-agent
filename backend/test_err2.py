import asyncio
from src.server.app import get_brokerage_history

async def test():
    res = await get_brokerage_history('Rollover IRA *5513', '2026-04-30', '2026-04-30')
    import json
    print(res.body.decode('utf-8'))

asyncio.run(test())
