import asyncio, sys, os, traceback
sys.path.append(os.path.abspath('backend'))
from src.tools.finance import get_macro_symbols
async def main():
    try:
        res = await get_macro_symbols.ainvoke({'fast_update': True})
    except Exception as e:
        traceback.print_exc()
if __name__ == '__main__':
    asyncio.run(main())
