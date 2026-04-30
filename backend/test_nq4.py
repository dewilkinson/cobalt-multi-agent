import asyncio
import traceback
from datetime import datetime
from src.tools.finance import get_macro_symbols, _fetch_direct_sparkline, _extract_ticker_data, _bucket_sparkline_data
async def test():
    try:
        from src.services.macro_registry import macro_registry
        macros = macro_registry.get_macros()
        df = await _fetch_direct_sparkline()
        nq_df = _extract_ticker_data(df, 'NQ=F')
        print('nq_df empty?', nq_df.empty)
        s_vals = _bucket_sparkline_data(nq_df, datetime.now(), 26450.25, 20, 100)
        print('Sparkline:', s_vals)
    except Exception as e:
        print('Error:', e)
        traceback.print_exc()
asyncio.run(test())
