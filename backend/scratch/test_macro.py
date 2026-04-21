import asyncio
import json
import logging

logging.basicConfig(level=logging.DEBUG)

async def test():
    from src.tools.finance import get_macro_symbols
    result = await get_macro_symbols.ainvoke({"fast_update": False})
    print("\n--- RESULTS ---")
    parsed = json.loads(result)
    for row in parsed.get("rows", []):
        print(row)

if __name__ == "__main__":
    asyncio.run(test())
