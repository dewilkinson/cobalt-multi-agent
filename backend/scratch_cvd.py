import asyncio
import os
import sys

# Add backend to path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tools.scanner import calculate_heuristic_cvd

async def main():
    print("Testing Heuristic CVD calculation for SPY...")
    is_trap = await asyncio.to_thread(calculate_heuristic_cvd, "SPY", 21)
    print(f"CVD Trap for SPY: {is_trap}")
    
    print("Testing Heuristic CVD calculation for NVDA...")
    is_trap_nvda = await asyncio.to_thread(calculate_heuristic_cvd, "NVDA", 21)
    print(f"CVD Trap for NVDA: {is_trap_nvda}")

if __name__ == "__main__":
    asyncio.run(main())
