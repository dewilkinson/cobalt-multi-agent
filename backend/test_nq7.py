import asyncio
import pandas as pd
from src.tools.finance import get_macro_symbols, _fetch_direct_sparkline, _extract_ticker_data
async def test():
    from src.services.macro_registry import macro_registry
    try:
        macros = macro_registry.get_macros()
        data_5m = await _fetch_direct_sparkline()
        print('Raw NQ NAs:', data_5m['Close']['NQ=F'].isna().sum(), 'len:', len(data_5m))
        data_5m = data_5m.fillna(method='ffill')
        print('fFill NQ NAs:', data_5m['Close']['NQ=F'].isna().sum())
        df = _extract_ticker_data(data_5m, 'NQ=F')
        col = 'Close' if 'Close' in df.columns else 'close'
        print('Extracted NQ NAs:', df[col].isna().sum())
        print('After dropna:', len(df[col].dropna()))
    except Exception as e:
        print(e)
asyncio.run(test())
