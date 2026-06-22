import asyncio
import json
import logging
import sys
import os
import pandas as pd
import yfinance
from datetime import datetime, timedelta

# Adjust sys.path to resolve backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from src.tools.finance import _extract_ticker_data

logging.basicConfig(level=logging.INFO)

def _bucket_sparkline_data_modified(df: pd.DataFrame, ref_time: datetime, current_price: float, num_points: int = 20, span_minutes: int = 390, session_mode: bool = False, step_minutes: int = 5) -> list:
    if df.empty:
        if session_mode:
            return [{"v": round(current_price, 4), "is_prev": False}] * num_points
        return [round(current_price, 4)] * num_points

    col = "Close" if "Close" in df.columns else "close"
    
    # Check for duplicated columns safely
    target_data = df[col]
    if isinstance(target_data, pd.DataFrame):
        target_data = target_data.iloc[:, 0]
        
    # Crucial Fix: Drop NaN values that leak from multi-ticker batch unions
    target_data = target_data.dropna().sort_index()
    
    if target_data.empty:
        if session_mode:
            return [{"v": round(current_price, 4), "is_prev": False}] * num_points
        return [round(current_price, 4)] * num_points

    if session_mode:
        # Align ref_time timezone to NY
        ref_time_ts = pd.Timestamp(ref_time)
        if ref_time_ts.tz is not None:
            ref_time_naive = ref_time_ts.tz_convert('America/New_York').tz_localize(None)
        else:
            ref_time_naive = ref_time_ts

        # Identify target date based on the latest available row's date
        latest_row_time = target_data.index[-1]
        target_date = latest_row_time.date()

        # Define pre-market start (4:00 AM) and post-market end (7:00 PM) for the target date
        start_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=4, minute=0)
        end_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=19, minute=0)

        # Set the active cutoff time for today's session
        if target_date < ref_time_naive.date():
            cutoff_dt = end_dt
        elif target_date == ref_time_naive.date():
            if ref_time_naive < start_dt:
                cutoff_dt = start_dt
            elif ref_time_naive > end_dt:
                cutoff_dt = end_dt
            else:
                cutoff_dt = ref_time_naive
        else:
            cutoff_dt = ref_time_naive

        # [FIX]: Anchor cutoff to the latest available data if it stopped trading before cutoff_dt
        print(f"DEBUG: original cutoff_dt={cutoff_dt}, latest_row_time={latest_row_time}")
        if latest_row_time < cutoff_dt:
            cutoff_dt = latest_row_time
            print(f"DEBUG: updated cutoff_dt to latest_row_time={cutoff_dt}")

        # Generate a list of naive NY datetimes going back in time
        dts = []
        curr = cutoff_dt

        def is_weekend(d):
            return d.weekday() >= 5

        while len(dts) < num_points:
            # Skip weekends
            if is_weekend(curr):
                curr = datetime.combine(curr.date(), datetime.min.time()).replace(hour=18, minute=55)
                while is_weekend(curr):
                    curr -= timedelta(days=1)
                continue

            # Skip non-active hours (overnight)
            if curr.hour < 4:
                prev_day = curr - timedelta(days=1)
                curr = datetime.combine(prev_day.date(), datetime.min.time()).replace(hour=18, minute=55)
                continue

            if curr.hour >= 19:
                curr = datetime.combine(curr.date(), datetime.min.time()).replace(hour=18, minute=55)
                continue

            dts.append(curr)
            curr -= timedelta(minutes=step_minutes)

        dts.reverse()

        # Sample prices at each index
        output_values = []
        for i, dt in enumerate(dts):
            # Check if this point is in the previous session
            is_prev = dt.date() < target_date

            if i == num_points - 1:
                # Last slot is always the current real-time price
                output_values.append({"v": round(float(current_price), 4), "is_prev": is_prev})
            else:
                val = target_data.asof(dt)
                if pd.isna(val):
                    output_values.append(None)
                else:
                    output_values.append({"v": round(float(val), 4), "is_prev": is_prev})

        return output_values

async def main():
    ticker = "^VIX"
    print("Downloading ^VIX data...")
    # Simulate batch download of 1m data
    data_5m = yfinance.download([ticker], period="2d", interval="1m", prepost=True, progress=False, threads=False)
    
    # Apply timezone alignment mapping from finance.py
    try:
        data_5m.index = pd.to_datetime(data_5m.index, utc=True).tz_convert('America/New_York').tz_localize(None)
    except Exception as e:
        data_5m.index = pd.to_datetime(data_5m.index).tz_localize(None)
        
    df = _extract_ticker_data(data_5m, ticker)
    
    ref_time = datetime.now()
    current_price = 17.68
    
    print(f"Ref time: {ref_time}")
    print("Running _bucket_sparkline_data_modified...")
    sparkline_values = _bucket_sparkline_data_modified(df, ref_time, current_price, num_points=32, span_minutes=240, session_mode=True, step_minutes=5)
    
    print("Resulting sparkline values:")
    print(json.dumps(sparkline_values, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
