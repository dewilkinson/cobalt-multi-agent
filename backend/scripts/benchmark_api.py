import asyncio
import time
import httpx
import sys

async def hit_api(ticker: str):
    print(f"\n--- Testing API Route for: {ticker} ---")
    url = "http://localhost:8000/api/vli/action-plan"
    payload = {"text": f"get smc analysis for {ticker}", "direct_mode": True}
    
    t1 = time.time()
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"FAILED: {e}")
        return
        
    t2 = time.time()
    print(f"[{ticker}] Resolution Latency: {t2 - t1:.2f} seconds")
    print(f"Response snippet: {str(data.get('response', ''))[:100]}...\n")

async def main():
    print("VLI LangGraph Pipeline Cold/Warm Benchmarks\n")
    # All completely distinct symbols to avoid LLM context caching & DF backend caching
    tickers = ["AAPL", "NVDA", "META"]
    for t in tickers:
        await hit_api(t)
        
    print("\nBenchmark Complete.")

if __name__ == "__main__":
    asyncio.run(main())
