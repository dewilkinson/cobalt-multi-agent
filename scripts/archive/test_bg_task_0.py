import threading
import asyncio
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_daily_morning_analysis():
    logger.info("[BG_ANALYST] Triggering 6:00 AM Morning Market Scan.")
    print("SUCCESS")

def bg_task():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_daily_morning_analysis())
    loop.close()

threading.Thread(target=bg_task, daemon=True).start()
time.sleep(1)
