import asyncio
import pandas as pd
from src.tools.finance import get_macro_symbols
async def test():
    print('Calling get_macro_symbols...')
    r = await get_macro_symbols.coroutine(fast_update=False)
    import json; print(json.loads(r)['rows'][1])
asyncio.run(test())
