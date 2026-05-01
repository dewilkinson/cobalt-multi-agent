import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

def get_sparkline_debug():
    df = yf.download(['SPY', 'QQQ'], period='2d', interval='1m', group_by='ticker', progress=False)
    ref_time = datetime(2026, 4, 15, 16, 0)
    
    data_5m = df[df.index <= pd.Timestamp(ref_time).tz_localize('America/New_York').tz_convert('UTC')]
    print("Filtered data_5m index max:", data_5m.index.max())
    
    def extract(d, tick):
        return d[tick].dropna(how="all").copy()
    
    def bucket(d, ref_time):
        col = 'Close'
        try:
            if d.index.tz is None:
                d.index = pd.to_datetime(d.index).tz_localize('UTC')
            d.index = d.index.tz_convert('America/New_York').tz_localize(None).as_unit('ns')
        except Exception as e:
            d.index = pd.to_datetime(d.index).tz_localize(None).as_unit('ns')
        
        temp_series = d[col].sort_index()
        start_time = ref_time - timedelta(minutes=390)
        target_index = pd.date_range(start=start_time, end=ref_time, periods=20)
        values = []
        for i, target_time in enumerate(target_index):
            val = temp_series.asof(target_time)
            val_idx = temp_series.index.searchsorted(target_time, side='right') - 1
            if val_idx < 0:
                values.append(None)
                continue
            val_ts = temp_series.index[val_idx]
            if val_ts.date() < target_time.date() and i < len(target_index) - 1:
                values.append(None)
                continue
            values.append(val)
        return values
        
    print("SPY:")
    spy_df = extract(data_5m, 'SPY')
    print("SPY values:", bucket(spy_df, ref_time))
    print("QQQ:")
    qqq_df = extract(data_5m, 'QQQ')
    print("QQQ values:", bucket(qqq_df, ref_time))

get_sparkline_debug()
