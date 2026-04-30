import asyncio
from src.tools.finance import get_macro_symbols
async def test():
    res = await get_macro_symbols.coroutine(fast_update=False)
    print(res[:1000])
asyncio.run(test())
