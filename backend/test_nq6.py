import asyncio
import pandas as pd
from src.tools.finance import get_macro_symbols, _extract_ticker_data
import src.tools.finance
async def test():
    from src.services.macro_registry import macro_registry
    # mock _bucket_sparkline_data to print target_data.empty
    original = src.tools.finance._bucket_sparkline_data
    def mock_bucket(df, ref_time, price, num_points=20, span_minutes=100):
        col = 'Close' if 'Close' in df.columns else 'close'
        td = df[col]
        print(df.columns)
        print('RAW NAs:', td.isna().sum(), 'TOTAL:', len(td))
        return original(df, ref_time, price, num_points, span_minutes)
    src.tools.finance._bucket_sparkline_data = mock_bucket
    await get_macro_symbols.coroutine(fast_update=False)
asyncio.run(test())
