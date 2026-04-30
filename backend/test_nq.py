import asyncio
import traceback
from src.tools.finance import get_macro_symbols
async def test():
    try:
        res = await get_macro_symbols.coroutine(fast_update=False)
        import json
        d = json.loads(res)['rows']
        for r in d:
            print(r[1], 'Start:', r[5]['value'][0], 'End:', r[5]['value'][-1])
    except Exception as e:
        print('Error:', e)
        traceback.print_exc()
asyncio.run(test())
