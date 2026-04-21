import asyncio
import logging
logging.basicConfig(level=logging.ERROR)
from src.tools.scanner import _run_activity_pulse_impl

async def test():
    res = await _run_activity_pulse_impl(watchlist='["SHEN", "AAPL", "CODI"]')
    print(res)

asyncio.run(test())
