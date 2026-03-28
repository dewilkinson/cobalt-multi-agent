import asyncio
import logging
import sys
from src.tools.macros import get_macro_data

# Silence logger for clean test output
logging.getLogger("src.tools.finance").setLevel(logging.ERROR)
logging.getLogger("src.tools.macros").setLevel(logging.ERROR)

async def run_final_validation():
    print("🚀 Running Production Macro Validation...")
    print("Testing get_macro_data() pipeline...")
    
    try:
        results = await get_macro_data()
        
        if not results:
            print("❌ CRITICAL FAILURE: get_macro_data() returned empty list.")
            sys.exit(1)
            
        print(f"✅ Success: Received {len(results)} macro records.")
        
        # Validation checks
        zero_prices = [r['label'] for r in results if r['price'] == 0]
        valid_prices = [r['label'] for r in results if r['price'] > 0]
        
        print(f"📊 Live Prices: {', '.join(valid_prices)}")
        
        if len(zero_prices) > 3:
            print(f"❌ FAILURE: Too many zero prices detected: {', '.join(zero_prices)}")
            sys.exit(1)
            
        # Specific check for key indices
        vital_indices = ["SPY", "VIX", "TNX"]
        for v in vital_indices:
            item = next((r for r in results if r['label'] == v), None)
            if not item or item['price'] == 0:
                print(f"❌ CRITICAL FAILURE: Vital index '{v}' is missing or has zero price.")
                sys.exit(1)
            else:
                print(f"✨ {v} Verified: {item['price']:.2f}")

        print("\n🏆 MACRO PIPELINE VALIDATED SUCCESSFULLY!")
        
    except Exception as e:
        print(f"❌ CRITICAL EXCEPTION: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_final_validation())
