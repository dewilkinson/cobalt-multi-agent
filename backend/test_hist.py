import asyncio
import sys
import os

sys.path.append(os.path.dirname(__file__))

from src.tools.finance import _fetch_stock_history
import yfinance as yf
from src.tools.scanner import calculate_sortino_ratio
from src.tools.indicators import calculate_downside_deviation
import numpy as np

def main():
    # Scanner way
    df1 = yf.download(['STM'], period='2d', interval='5m', progress=False)
    df1_rets = df1['Close'].pct_change().dropna()
    sortino1 = calculate_sortino_ratio(df1_rets, annual_rf=0.0, interval='5m')
    
    # LLM way
    df2 = _fetch_stock_history('STM', '2d', '5m')
    df2.columns = [str(c).lower() for c in df2.columns]
    df2_rets = df2['close'].pct_change().dropna()
    downside_dev = calculate_downside_deviation(df2_rets, 0.0)
    sortino2 = ((df2_rets.mean() - 0.0) / downside_dev) * np.sqrt(78*252) if downside_dev > 0 else 0
    
    print('yf.download sortino (Scanner):', sortino1)
    print('_fetch_stock_history sortino (LLM):', sortino2)

if __name__ == '__main__':
    main()
