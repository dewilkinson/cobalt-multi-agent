import asyncio
from src.tools.finance import get_macro_symbols
async def test():
    r = await get_macro_symbols.coroutine(fast_update=False)
    import json
    d = json.loads(r)['rows']
    print([row[5]['value'] for row in d if row[1] == 'NQ=F'])
asyncio.run(test())
