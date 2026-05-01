import asyncio, sys, os, json
sys.path.append(os.path.abspath('backend'))
from src.tools.finance import _fetch_direct_sparkline

async def main():
    df = await _fetch_direct_sparkline(['SPY', 'QQQ', 'GLDM', '^VIX', '^TNX', 'DX-Y.NYB'])
    print(df.columns)

if __name__ == '__main__':
    asyncio.run(main())
