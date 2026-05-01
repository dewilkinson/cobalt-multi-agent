import asyncio, sys, os
import pandas as pd
sys.path.append(os.path.abspath('backend'))
from src.tools.finance import _fetch_direct_sparkline, _extract_ticker_data

async def main():
    data_5m = await _fetch_direct_sparkline(['ES=F', 'NQ=F', 'GC=F', 'CL=F', 'ZN=F', 'BTC-USD'])
    print("data_5m columns:")
    print(data_5m.columns)
    df = _extract_ticker_data(data_5m, 'GC=F')
    print("Extracted GC=F columns:")
    print(df.columns)
    print("Is GC=F empty?", df.empty)

if __name__ == '__main__':
    asyncio.run(main())
