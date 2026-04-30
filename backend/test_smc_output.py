import asyncio
import sys
sys.path.insert(0, './')
from src.tools.smc import get_smc_analysis

import json

async def main():
    res = await get_smc_analysis.coroutine(ticker="MSFT", period="1y", interval="1d")
    
    print("-" * 50)
    print(f"RAW STRING LENGTH: {len(res)} characters")
    
    try:
        parsed = json.loads(res)
        print(f"DECODED LIST SIZE: {len(parsed)} records")
        
        if len(parsed) > 50:
            print("[CRITICAL WARNING] - Parsed list exceeds 50 items and will hit the ANTI-ROT Regex cutoff in reporter.py!" )
            
        if len(parsed) > 0:
            print("\n[FIRST RECORD PREVIEW]:")
            print(json.dumps(parsed[0], indent=2))
            
            print("\n[LAST RECORD PREVIEW]:")
            print(json.dumps(parsed[-1], indent=2))
        else:
            print("[ERROR]: Decoded list is empty []!")
    except Exception as e:
        print(f"JSON PARSE ERROR: {e}")
    print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
