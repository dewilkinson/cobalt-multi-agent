import asyncio
from src.tools.finance import get_stock_quote

async def verify_vix():
    print("DEBUG: Calling get_stock_quote.func('VIX')...")
    try:
        # Note: calling the .func attribute because it's a @tool
        result = await get_stock_quote.func("VIX")
        if isinstance(result, dict):
            print(f"DEBUG: SUCCESS - Retrieved VIX: {result['symbol']} @ {result['price']}")
        else:
            print(f"DEBUG: FAILURE - Result: {result}")
    except Exception as e:
        print(f"DEBUG: EXCEPTION - {str(e)}")

if __name__ == "__main__":
    asyncio.run(verify_vix())
