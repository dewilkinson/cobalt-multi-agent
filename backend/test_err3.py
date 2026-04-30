import asyncio
from src.server.app import get_brokerage_history

async def test():
    for acct in ['97473262-5359-4118-b565-4e4c0b8a4293', 'mock-fidelity-1', 'Rollover IRA *5513', 'Health Savings Account *6937']:
        res = await get_brokerage_history(acct, '2026-04-30', '2026-04-30')
        print(f'{acct}: {res.body.decode()[:100]}')

asyncio.run(test())
