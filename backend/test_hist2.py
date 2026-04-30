import asyncio
import sys
import os

sys.path.append(os.path.dirname(__file__))

from src.tools.finance import _fetch_stock_history
import yfinance as yf
import numpy as np

def main():
    # Scanner way
    df1 = yf.download(['STM'], period='2d', interval='5m', progress=False)
    # LLM way
    df2 = _fetch_stock_history('STM', '2d', '5m')
    
    # We must properly index df1 since it's a MultiIndex when downloading 1 ticker sometimes, or a single index.
    # yf.download with 1 ticker returns a normal DataFrame.
    
    if isinstance(df1.columns, pd.MultiIndex):
        c1_first = float(df1['Close', 'STM'].iloc[0])
        c1_last = float(df1['Close', 'STM'].iloc[-1])
    else:
        c1_first = float(df1['Close'].iloc[0])
        c1_last = float(df1['Close'].iloc[-1])
        
    c2_first = float(df2['Close'].iloc[0])
    c2_last = float(df2['Close'].iloc[-1])
    
    print('df1 len:', len(df1), 'first close:', c1_first, 'last close:', c1_last)
    print('df2 len:', len(df2), 'first close:', c2_first, 'last close:', c2_last)

if __name__ == '__main__':
    import pandas as pd
    main()
