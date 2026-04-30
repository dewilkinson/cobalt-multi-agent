import asyncio
import traceback
from src.tools.finance import get_volume_profile, get_sortino_ratio, get_volatility_atr, get_stock_quote

async def test():
    try:
        res = get_volume_profile.invoke({'ticker': 'ADTN', 'period': '1d', 'interval': '5m'})
        print("get_volume_profile:", res[:100])
    except Exception as e:
        print("get_volume_profile EXCEPTION:")
        traceback.print_exc()

    try:
        res = get_sortino_ratio.invoke({'ticker': 'ADTN', 'period': '1d', 'interval': '5m'})
        print("get_sortino_ratio:", res)
    except Exception as e:
        print("get_sortino_ratio EXCEPTION:")
        traceback.print_exc()

    try:
        res = get_volatility_atr.invoke({'ticker': 'ADTN', 'period': '1d', 'interval': '5m'})
        print("get_volatility_atr:", res[:100])
    except Exception as e:
        print("get_volatility_atr EXCEPTION:")
        traceback.print_exc()

    try:
        res = get_stock_quote.invoke({'ticker': 'ADTN'})
        print("get_stock_quote:", res[:100])
    except Exception as e:
        print("get_stock_quote EXCEPTION:")
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test())
