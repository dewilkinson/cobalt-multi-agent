import asyncio
import json
import logging
from src.tools.scanner import _run_activity_pulse_impl

logging.basicConfig(level=logging.DEBUG)

async def test():
    res = await _run_activity_pulse_impl('{}', json.dumps(['SIBN']))
    print(res)

asyncio.run(test())
