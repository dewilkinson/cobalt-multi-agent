import yfinance as yf
import pandas as pd
from src.tools.scanner import calculate_sortino_ratio

def main():
    df_false = yf.download(['STM'], period='2d', interval='5m', progress=False, prepost=False)
    df_true = yf.download(['STM'], period='2d', interval='5m', progress=False, prepost=True)
    
    c_false = float(df_false['Close'].iloc[-1])
    c_true = float(df_true['Close'].iloc[-1])
    
    print('prepost=False len:', len(df_false), 'last:', c_false)
    print('prepost=True len:', len(df_true), 'last:', c_true)
    
    rets_false = df_false['Close'].pct_change().dropna()
    rets_true = df_true['Close'].pct_change().dropna()
    
    s_false = calculate_sortino_ratio(rets_false, annual_rf=0.0, interval='5m')
    s_true = calculate_sortino_ratio(rets_true, annual_rf=0.0, interval='5m')
    
    print('sortino False:', s_false)
    print('sortino True:', s_true)

if __name__ == '__main__':
    main()
