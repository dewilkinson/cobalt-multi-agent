import asyncio
from src.server.app import _invoke_vli_agent
import logging
logging.basicConfig(level=logging.INFO)

async def run():
    print("Starting agent...")
    try:
        res = await _invoke_vli_agent('run market scan')
        print("FINISHED successfully:")
        print(res)
    except Exception as e:
        print("EXCEPTION:", e)

if __name__ == '__main__':
    asyncio.run(run())
