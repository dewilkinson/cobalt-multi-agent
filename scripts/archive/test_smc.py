import asyncio
import pandas as pd
from smartmoneyconcepts import smc
from src.tools.finance import _fetch_batch_history, _extract_ticker_data

async def main():
    data = await asyncio.to_thread(_fetch_batch_history, ['AAPL'], '1mo', '1d')
    df = _extract_ticker_data(data, 'AAPL').tail(30).copy()
    df.columns = [c.lower() for c in df.columns]
    fvg = smc.fvg(df)
    print("FVG COLUMNS:", fvg.columns)
    print(fvg[fvg['FVG'] != 0].tail(2))

    swings = smc.swing_highs_lows(df, swing_length=3)
    ob = smc.ob(df, swings)
    print("OB COLUMNS:", ob.columns)
    print(ob[ob['OB'] != 0].tail(2))

asyncio.run(main())
