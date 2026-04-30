import asyncio
import os
import json
import logging
logging.basicConfig(level=logging.ERROR)

from src.tools.indicators import get_sortino_ratio
from src.tools.scanner import _run_activity_pulse_impl

async def test():
    print('VLI_TRADING_STYLE =', os.getenv('VLI_TRADING_STYLE'))
    print('ANALYSIS RESULT:')
    res = await get_sortino_ratio.ainvoke({'ticker':'SHEN'})
    print(res)

    print('\nSCANNER RESULT (PULSE):')
    res2 = await _run_activity_pulse_impl(watchlist='["SHEN"]')
    print(res2)

asyncio.run(test())
