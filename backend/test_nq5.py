import asyncio
import pandas as pd
from src.tools.finance import get_macro_symbols
async def test():
    res = await get_macro_symbols.coroutine(fast_update=False)
    import json
    data = json.loads(res)['rows']
    nq = [r for r in data if r[1] == 'NQ=F'][0]
    # sparkline is at index 5
    print('NQ=', nq[5]['value'])
asyncio.run(test())
