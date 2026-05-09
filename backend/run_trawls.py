import asyncio
import logging
from src.tools.sortino_sniper_trawl import run_background_trawl
from src.tools.shield_scanner_trawl import run_shield_trawl

async def main():
    logging.basicConfig(level=logging.INFO)
    print('Running SNIPER...')
    await run_background_trawl()
    print('Running SHIELD...')
    await run_shield_trawl.ainvoke({})
    print('Done!')

if __name__ == "__main__":
    asyncio.run(main())
