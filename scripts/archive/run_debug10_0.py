import asyncio, sys, os
import pandas as pd
sys.path.append(os.path.abspath('backend'))
from src.tools.finance import get_macro_symbols

async def main():
    res = await get_macro_symbols.ainvoke({'fast_update': True})
if __name__ == '__main__':
    asyncio.run(main())
