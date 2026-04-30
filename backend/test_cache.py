import asyncio
import time
from dotenv import load_dotenv
load_dotenv()

from src.graph.builder import build_graph
from langchain_core.messages import HumanMessage

async def run_analysis(app, ticker: str) -> float:
    state = {
        "messages": [HumanMessage(content=f"Analyze {ticker}")],
        "locale": "en-US",
        "research_topic": ticker,
        "final_report": "",
        "raw_data_mode": False
    }
    
    start_time = time.time()
    try:
        async for output in app.astream(state, {"recursion_limit": 50}):
            pass # Drain the generator
    except Exception as e:
        print(f"Graph failed for {ticker}:", e)
    
    end_time = time.time()
    return end_time - start_time

async def main():
    app = build_graph()
    
    # 1. RIVN - Cold
    print("Testing 1/3: RIVN (Cold cache expected...)")
    rivn_1 = await run_analysis(app, "RIVN")
    print(f"RIVN (Cold) Time: {rivn_1:.2f} seconds\n")
    
    # 2. MSFT - Cold
    print("Testing 2/3: MSFT (Cold cache expected...)")
    msft_1 = await run_analysis(app, "MSFT")
    print(f"MSFT (Cold) Time: {msft_1:.2f} seconds\n")
    
    # 3. RIVN - Warm
    print("Testing 3/3: RIVN (Warm cache expected...)")
    rivn_2 = await run_analysis(app, "RIVN")
    print(f"RIVN (Warm) Time: {rivn_2:.2f} seconds\n")
    
    print("-" * 30)
    print("Performance Summary:")
    print(f"1. RIVN (Cold):  {rivn_1:.2f}s")
    print(f"2. MSFT (Cold):  {msft_1:.2f}s")
    print(f"3. RIVN (Warm):  {rivn_2:.2f}s")
    print(f"Performance delta for RIVN cache: {rivn_1 - rivn_2:.2f}s saved.")

if __name__ == "__main__":
    asyncio.run(main())
