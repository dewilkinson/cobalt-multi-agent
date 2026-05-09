import asyncio
import logging

from src.tools.finance import get_stock_quote


async def verify():
    logging.basicConfig(level=logging.INFO)
    print("---  VLI Hybrid Resolver Manual Verification ---")

    # 1. Test Fast-Path (Diagnostic Mock)
    print("\n1. Testing Fast-Path (Mock Ticker)...")
    res1 = await get_stock_quote.coroutine("HIGH_VOL_MOCK", use_fast_path=True)
    print(f"Result: {res1}")
    assert res1.get("is_mock") is True

    # 2. Test Real Fast-Path (AAPL)
    print("\n2. Testing Real Fast-Path (AAPL)...")
    res2 = await get_stock_quote.coroutine("AAPL", use_fast_path=True)
    print(f"Result: {res2}")
    assert "price" in res2

    # 3. Test Fallback (Invalid Ticker)
    print("\n3. Testing Fallback (Invalid Ticker)...")
    res3 = await get_stock_quote.coroutine("INVALID_TICKER_12345")
    print(f"Result: {res3}")
    # Should trigger Snapper or return error

    print("\n---  Verification Complete ---")


if __name__ == "__main__":
    asyncio.run(verify())
