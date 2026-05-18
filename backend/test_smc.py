import sys
import io
from contextlib import redirect_stdout
with redirect_stdout(io.StringIO()):
    from smartmoneyconcepts import smc
import asyncio
import json
from src.tools.smc import _fetch_stock_history

async def run():
    df = await asyncio.to_thread(_fetch_stock_history, 'BCAR', '1y', '1d')
    df.columns = [c.lower() for c in df.columns]
    
    swings15 = smc.swing_highs_lows(df, swing_length=15)
    structure15 = smc.bos_choch(df, swings15)
    print("Swing 15 BOS:")
    print(structure15[structure15['BOS'].fillna(0) != 0].tail(3)[['BOS','Level']])
    print("Swing 15 CHOCH:")
    print(structure15[structure15['CHOCH'].fillna(0) != 0].tail(3)[['CHOCH','Level']])

asyncio.run(run())
