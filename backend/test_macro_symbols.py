import asyncio

from src.tools.finance import _extract_ticker_data, _fetch_batch_history


async def test_macros_logic():
    tickers = ["SPY", "^VIX", "^TNX", "DX-Y.NYB"]  # Corrected to the NYB symbol
    print(f"Testing yfinance for macros: {tickers}")

    # Try fetching as a batch
    df = _fetch_batch_history(tickers, "5d", "1d")
    print(f"Raw columns: {df.columns.tolist()}")

    for t in tickers:
        ticker_df = _extract_ticker_data(df, t)
        if ticker_df.empty:
            print(f"FAILED: {t} dataframe is EMPTY")
        else:
            last_row = ticker_df.iloc[-1]
            print(f"SUCCESS: {t} | Price: {last_row['Close']:.2f}")


if __name__ == "__main__":
    asyncio.run(test_macros_logic())
