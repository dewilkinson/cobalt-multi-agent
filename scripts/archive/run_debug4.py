import yfinance as yf
import pandas as pd
df1 = yf.download('SPY', period='1d', interval='1m')
df2 = yf.download('QQQ', period='1d', interval='1m')
combined = {'SPY': df1, 'QQQ': df2}
df = pd.concat(combined.values(), axis=1, keys=combined.keys())
print('Concat columns:')
print(df.columns)
res = df['SPY']
print('\ndf[SPY] columns:')
print(res.columns)
if isinstance(res.columns, pd.MultiIndex):
    res.columns = [c[0] for c in res.columns]
print('\nafter extraction:')
print(res.columns)
