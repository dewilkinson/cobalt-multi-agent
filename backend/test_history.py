import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from tools.finance import get_symbol_history_data


async def main():
    print("Testing get_symbol_history_data for SPY and ^VIX...")
    try:
        # Call the tool
        # In langchain_core.tools, tool objects are invoked with a dict of args
        report = await get_symbol_history_data.ainvoke({"symbols": ["SPY", "^VIX"], "period": "1d", "interval": "1h"})
        print("\n--- REPORT START ---")
        print(report)
        print("--- REPORT END ---\n")

        if "[ERROR]" in report:
            print("FAILED: Report contains errors.")
        elif "Close:" in report:
            print("SUCCESS: Report contains stock values.")
        else:
            print("WARNING: Report produced but structure is unexpected.")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(main())
