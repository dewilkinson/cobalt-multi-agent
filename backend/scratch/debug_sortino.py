import asyncio
import os
import yfinance as yf
import pandas as pd
import numpy as np

def calculate_sortino_ratio(returns: pd.Series, annual_rf: float = 0.0428, interval: str = "1d") -> float:
    if returns.empty or len(returns) < 2: return 0.0
    annual_factor = 252.0
    if interval == "5m": annual_factor = 78.0 * 252.0
    elif interval == "15m": annual_factor = 26.0 * 252.0
    periodic_rf = annual_rf / annual_factor
    avg_return = returns.mean()
    excess_returns = returns - periodic_rf
    downside_returns = excess_returns.copy()
    downside_returns[excess_returns > 0] = 0.0
    downside_std = np.sqrt(np.mean(downside_returns**2))
    if downside_std == 0: return 10.0 if avg_return > 0 else 0.0
    sortino = ((avg_return - periodic_rf) / downside_std) * np.sqrt(annual_factor)
    return round(float(sortino), 2)

async def test_scanner_sortino():
    data = yf.download(["QUIK"], period="2d", interval="5m", progress=False, prepost=True)
    returns = data['Close'].pct_change().dropna()
    print("Scanner sortino:", calculate_sortino_ratio(returns, 0.0, "5m"), "len:", len(returns))

async def test_finance_sortino():
    from src.tools.finance import _fetch_stock_history
    hist = _fetch_stock_history("QUIK", "2d", "5m")
    hist.columns = [str(c).lower() for c in hist.columns]
    returns = hist['close'].pct_change().dropna()
    print("Finance sortino:", calculate_sortino_ratio(returns, 0.0, "5m"), "len:", len(returns))

async def main():
    await test_scanner_sortino()
    await test_finance_sortino()

if __name__ == "__main__":
    asyncio.run(main())
