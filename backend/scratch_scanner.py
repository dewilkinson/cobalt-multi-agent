import asyncio
import sys
import logging
from src.tools.scanner import _run_activity_pulse_impl, _build_session_watchlist_impl

logging.basicConfig(level=logging.DEBUG)

async def main():
    print("Testing scanner in premarket mode...")
    watchlist = '["AAPL", "TSLA", "NVDA", "SPY", "CELH"]'
    result = await _run_activity_pulse_impl("{}", watchlist)
    print("Pulse Result:")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
