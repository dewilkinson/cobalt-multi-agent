import asyncio
import sys
import os

# add backend to path
sys.path.append(os.path.abspath('backend'))
from src.tools.scanner import _run_activity_pulse_impl

async def main():
    res = await _run_activity_pulse_impl(watchlist='["CODI"]')
    print("Result:", res)

asyncio.run(main())
