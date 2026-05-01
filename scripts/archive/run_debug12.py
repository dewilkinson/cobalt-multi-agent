import asyncio, sys, os, json
sys.path.append(os.path.abspath('backend'))
from src.tools.finance import get_macro_symbols

async def main():
    res = await get_macro_symbols.ainvoke({'fast_update': True})
    data = json.loads(res)['rows']
    for r in data:
        print(r[0])

if __name__ == '__main__':
    asyncio.run(main())
