import pandas as pd
import yfinance as yf

def safe_float(val, default=0.0):
    import math
    try:
        f = float(val)
        return default if math.isnan(f) else f
    except:
        return default

open_positions = {'EDSA': {'quantity': 2.0, 'total_cost': 20.0, 'average_cost': 10.0}}
tickers = list(open_positions.keys())
yf_to_raw = {}
yf_tickers = []
for t in tickers:
    yf_t = t
    if yf_t.startswith('/'):
        yf_t = yf_t[1:] + '=F'
    yf_tickers.append(yf_t)
    yf_to_raw[yf_t] = t

data = yf.download(yf_tickers, period="5d", group_by='ticker', threads=True, progress=False)

positions_payload = []
for yf_sym, sym in yf_to_raw.items():
    pdata = open_positions[sym]
    try:
        sym_data = data if len(yf_tickers) == 1 else data[yf_sym]
        
        # Handle yfinance single-ticker MultiIndex edge case
        if isinstance(sym_data.columns, pd.MultiIndex):
            try:
                close_col = sym_data['Close']
            except KeyError:
                close_col = sym_data[('Close', yf_sym)] if ('Close', yf_sym) in sym_data.columns else sym_data.iloc[:, 0]
        else:
            close_col = sym_data['Close'] if 'Close' in sym_data.columns else sym_data.iloc[:, 0]
            
        # Extract raw scalar to prevent pandas single-element Series TypeError
        last_val = close_col.iloc[-1]
        prev_val = close_col.iloc[-2] if len(close_col) > 1 else last_val
        
        if isinstance(last_val, pd.Series):
            last_val = last_val.iloc[0]
        if isinstance(prev_val, pd.Series):
            prev_val = prev_val.iloc[0]
            
        last_price = safe_float(last_val)
        prev_close = safe_float(prev_val)
        
        last_time_obj = sym_data.index[-1]
        last_time_str = last_time_obj.strftime('%Y-%m-%d 16:00') if hasattr(last_time_obj, 'strftime') else 'Unknown'
        
        qty = safe_float(pdata['quantity'])
        avg_cost = safe_float(pdata['average_cost'])
        total_cost = safe_float(pdata['total_cost'])
        current_value = qty * last_price
        
        todays_gl_dol = (last_price - prev_close) * qty
        todays_gl_pct = ((last_price - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
        
        total_gl_dol = current_value - total_cost
        total_gl_pct = (total_gl_dol / total_cost * 100) if total_cost > 0 else 0.0
        
        positions_payload.append({
            "symbol": sym,
            "qty": qty,
        })
    except Exception as e:
        print(f"EXCEPTION: {e}")

print("Payload:", positions_payload)
