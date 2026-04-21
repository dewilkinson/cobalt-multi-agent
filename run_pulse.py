import asyncio, sys, os
sys.path.append(os.path.abspath('backend'))
from src.server.app import poll_market_pulse

if __name__ == '__main__':
    print("Triggering manual poll_market_pulse...")
    asyncio.run(poll_market_pulse())
    print("Pulse complete.")
