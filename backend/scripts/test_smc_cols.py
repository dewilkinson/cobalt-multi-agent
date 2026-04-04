import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.tools.finance import _fetch_batch_history, _extract_ticker_data
import smartmoneyconcepts as smc

def test_columns():
    df = _extract_ticker_data(_fetch_batch_history(["XRP-USD"], "1mo", "1d"), "XRP-USD")
    df.columns = [c.lower() for c in df.columns]
    swings = smc.swing_highs_lows(df, swing_length=5)
    
    struct = smc.bos_choch(df, swings)
    ob = smc.ob(df, swings)
    fvg = smc.fvg(df)
    liq = smc.liquidity(df, swings)

    print("STRUCT COLUMNS:", struct.columns.tolist())
    print("OB COLUMNS:", ob.columns.tolist())
    print("FVG COLUMNS:", fvg.columns.tolist())
    print("LIQ COLUMNS:", liq.columns.tolist())
    
    if len(ob[ob["OB"]!=0]) > 0:
        print("LATEST OB:", ob[ob["OB"]!=0].iloc[-1].to_dict())
    if len(fvg[fvg["FVG"]!=0]) > 0:
        print("LATEST FVG:", fvg[fvg["FVG"]!=0].iloc[-1].to_dict())

if __name__ == "__main__":
    test_columns()
