import asyncio
import os
import sys
import json

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

# Force yfinance provider
os.environ["DATA_PROVIDER"] = "yfinance"

from src.tools.macros import get_macro_data

async def main():
    data = await get_macro_data()
    for item in data:
        if item["label"] == "QQQ":
            print(json.dumps(item, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
