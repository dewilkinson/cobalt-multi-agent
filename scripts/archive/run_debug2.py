import pandas as pd
df1 = pd.DataFrame({'Close': [1]})
df2 = pd.DataFrame({'Close': [2], 'Volume': [100]})
combined = {'SPY': df1, 'QQQ': df2}
df = pd.concat(combined.values(), axis=1, keys=combined.keys())
print('Concat result columns:')
print(df.columns)
res = df['SPY']
print('\ndf[SPY] columns:')
print(res.columns)
if isinstance(res.columns, pd.MultiIndex):
    res.columns = [c[0] for c in res.columns]
print('\nafter extraction:')
print(res.columns)
