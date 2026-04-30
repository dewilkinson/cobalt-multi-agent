import asyncio

from src.tools.finance import _fetch_batch_history, get_stock_quote


async def test_quote():
    print("Testing get_stock_quote('SPY')...")
    res = await get_stock_quote("SPY")
    print(f"Result:\n{res}")

    print("\nTesting _fetch_batch_history(['SPY'])...")
    df = _fetch_batch_history(["SPY"])
    print(f"Columns: {df.columns}")
    print(f"Head:\n{df.head()}")


if __name__ == "__main__":
    asyncio.run(test_quote())
