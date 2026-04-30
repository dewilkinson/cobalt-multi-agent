import asyncio
import sys
import logging
import json

sys.path.insert(0, './')

from src.server.app import _invoke_vli_agent

logging.basicConfig(level=logging.INFO)

async def main():
    print("Testing _invoke_vli_agent acting like the UI...")
    res, state = await _invoke_vli_agent("issuing the full get smc analysis for MSFT", None, False)
    
    print("=" * 60)
    print(f"RESPONSE TYPE: {type(res)}")
    print(f"RESPONSE VALUE:\n{res}")

if __name__ == "__main__":
    asyncio.run(main())
