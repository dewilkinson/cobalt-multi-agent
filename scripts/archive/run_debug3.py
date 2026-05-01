import yfinance as yf
df1 = yf.download('SPY', period='1d', interval='1m')
print(df1.columns)
