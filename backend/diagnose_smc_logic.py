import asyncio
import yfinance as yf
import pandas as pd
import numpy as np

# PURE LOGIC FROM src/tools/smc.py
def find_fvg(df: pd.DataFrame):
    fvgs = []
    for i in range(2, len(df)):
        # Bullish FVG (Gap between Candle 1's High and Candle 3's Low)
        if df['High'].iloc[i-2] < df['Low'].iloc[i]:
            fvgs.append({"type": "Bullish", "top": df['Low'].iloc[i], "bottom": df['High'].iloc[i-2], "index": i-1})
        # Bearish FVG (Gap between Candle 1's Low and Candle 3's High)
        elif df['Low'].iloc[i-2] > df['High'].iloc[i]:
            fvgs.append({"type": "Bearish", "top": df['Low'].iloc[i-2], "bottom": df['High'].iloc[i], "index": i-1})
    return fvgs

def find_structure(df: pd.DataFrame):
    recent_high = df['High'].max()
    recent_low = df['Low'].min()
    current_price = df['Close'].iloc[-1]
    bias = "Bullish" if current_price > (recent_high + recent_low)/2 else "Bearish"
    return {"bias": bias, "high": recent_high, "low": recent_low}

async def diagnose():
    symbol = "GLDM"
    print(f"--- Diagnosing SMC Logic for {symbol} ---")
    stock = yf.Ticker(symbol)
    df = stock.history(period="60d")
    
    if df.empty:
        print("ERROR: DATA IS EMPTY. yfinance might be failing or the ticker is wrong.")
        return
        
    print(f"Data retrieved: {len(df)} bars.")
    
    fvgs = find_fvg(df)
    struct = find_structure(df)
    
    print(f"SMC Bias: {struct['bias']}")
    print(f"FVGs found: {len(fvgs)}")
    for fvg in fvgs[-3:]:
        print(f"  - {fvg['type']} @ {fvg['bottom']:.2f} - {fvg['top']:.2f}")

if __name__ == "__main__":
    asyncio.run(diagnose())
