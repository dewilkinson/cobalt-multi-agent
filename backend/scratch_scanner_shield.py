import logging
logging.basicConfig(level=logging.DEBUG)
import asyncio
from src.tools.shield_scanner_trawl import run_shield_trawl

async def main():
    res = await run_shield_trawl.ainvoke({})
    print("RES:", res)

if __name__ == "__main__":
    asyncio.run(main())
