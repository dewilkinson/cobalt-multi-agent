import pandas as pd
df1 = pd.DataFrame({'Close': [1]})
df2 = pd.DataFrame({'Close': [2]})
combined = {'SPY': df1, 'QQQ': df2}
df = pd.concat(combined.values(), axis=1, keys=list(combined.keys()))
df = df[df.index <= 0]
print(type(df.columns))
