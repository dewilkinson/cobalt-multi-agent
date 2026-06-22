import pandas as pd
import yfinance as yf
import numpy as np
import sys
import os

# Add backend root to path so we can import src.tools
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
from src.tools.indicators import (
    calculate_va_bands, calculate_dmi, calculate_cmf, calculate_atr,
    calculate_apex_sortino, calculate_intraday_rvol, calculate_cvd_divergence
)

def main():
    print("Fetching sample data (AAPL, 5m, 5d)...")
    ticker = yf.Ticker("AAPL")
    df = ticker.history(period="5d", interval="5m")
    df.columns = [c.lower() for c in df.columns]
    
    print(f"Data shape: {df.shape}")
    
    print("\n1. Testing ATR...")
    df_atr = calculate_atr(df.copy(), length=14, smoothing="RMA")
    print(f"ATR tail:\n{df_atr['atr'].tail(3)}")
    
    print("\n2. Testing VA Bands...")
    df_va = calculate_va_bands(df.copy(), tick_size=0.10)
    print(f"VA Bands tail:\n{df_va[['poc', 'vah', 'val']].tail(3)}")
    
    print("\n3. Testing DMI...")
    df_dmi = calculate_dmi(df.copy())
    print(f"DMI tail:\n{df_dmi[['adx', '+di', '-di']].tail(3)}")
    
    print("\n4. Testing CMF...")
    df_cmf = calculate_cmf(df.copy())
    print(f"CMF tail:\n{df_cmf['cmf'].tail(3)}")
    
    print("\n5. Testing Apex Sortino...")
    df_sort = calculate_apex_sortino(df.copy())
    print(f"Sortino tail:\n{df_sort[['operational_sortino', 'tactical_sortino']].tail(3)}")
    
    print("\n6. Testing Intraday RVOL...")
    df_rvol = calculate_intraday_rvol(df.copy())
    print(f"RVOL tail:\n{df_rvol[['rvol', 'rvol_ema']].tail(3)}")
    
    print("\n7. Testing CVD Divergence...")
    df_cvd = calculate_cvd_divergence(df.copy())
    print(f"CVD tail:\n{df_cvd[['cvd_hist', 'pivot_high', 'pivot_low']].tail(3)}")

    print("\nAll conversions executed successfully!")

if __name__ == "__main__":
    main()
