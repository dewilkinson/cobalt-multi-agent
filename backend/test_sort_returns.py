
import asyncio
import pandas as pd
from src.tools.indicators import _fetch_stock_history, calculate_downside_deviation
from src.tools.scanner import calculate_sortino_ratio
import yfinance as yf
import numpy as np

def test():
    # 1. ANALYSIS TOOL
    df = _fetch_stock_history('SHEN', '2d', '5m')
    df.columns = [str(c).lower() for c in df.columns]
    returns1 = df['close'].pct_change().dropna()
    downside_dev = calculate_downside_deviation(returns1, 0.0)
    s1 = ((returns1.mean() - 0.0) / downside_dev) * np.sqrt(78 * 252) if downside_dev > 0 else 0
    print('Analysis ret length:', len(returns1), 'Sortino:', s1)

    # 2. SCANNER TOOL
    ticker_obj = yf.Ticker('SHEN')
    hist_sortino = ticker_obj.history(period='2d', interval='5m')
    returns2 = hist_sortino['Close'].pct_change().dropna()
    s2 = calculate_sortino_ratio(returns2, annual_rf=0.0, interval='5m')
    print('Scanner ret length:', len(returns2), 'Sortino:', s2)

test()

