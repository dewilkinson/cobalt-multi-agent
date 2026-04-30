import asyncio
import pandas as pd
from src.tools.finance import get_macro_symbols, _bucket_sparkline_data
import src.tools.finance
async def test():
    from src.services.macro_registry import macro_registry
    original = src.tools.finance._bucket_sparkline_data
    def mock_bucket(df, ref_time, price, num_points=32, span_minutes=240):
        res = original(df, ref_time, price, num_points, span_minutes)
        col = 'Close' if 'Close' in df.columns else 'close'
        print('DF cols:', df.columns, 'RES len:', len(res))
        print(res)
        return res
    src.tools.finance._bucket_sparkline_data = mock_bucket
    await get_macro_symbols.coroutine(fast_update=False)
asyncio.run(test())
