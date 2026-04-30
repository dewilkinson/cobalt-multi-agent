import asyncio
import pandas as pd, yfinance as yf
async def test():
    df = await asyncio.to_thread(yf.download, 'GC=F', period='2d', interval='1m', prepost=False, progress=False, threads=False)
    try:
        df.index = pd.to_datetime(df.index, utc=True).tz_convert('America/New_York').tz_localize(None)
    except Exception:
        pass
    print('GC Fallback MAX:', df.index.max())
asyncio.run(test())
