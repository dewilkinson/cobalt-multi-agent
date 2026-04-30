import asyncio
import pandas as pd
from src.tools.finance import get_macro_symbols, _bucket_sparkline_data
import src.tools.finance
async def test():
    from src.services.macro_registry import macro_registry
    original = src.tools.finance._bucket_sparkline_data
    def mock_bucket(df, ref_time, price, num_points=32, span_minutes=240):
        col = 'Close' if 'Close' in df.columns else 'close'
        target_data = df[col].dropna()
        temp_series = target_data.sort_index()
        print('TICKER MAX TIME:', temp_series.index.max(), 'REF:', ref_time)
        return original(df, ref_time, price, num_points, span_minutes)
    src.tools.finance._bucket_sparkline_data = mock_bucket
    await get_macro_symbols.coroutine(fast_update=False)
asyncio.run(test())
