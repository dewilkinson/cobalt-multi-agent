import asyncio
import logging
logging.basicConfig(level=logging.ERROR)
from src.tools.scanner import _run_activity_pulse_impl

async def test():
    res = await _run_activity_pulse_impl(watchlist='["CODI"]')
    print(res)

if __name__ == "__main__":
    asyncio.run(test())
