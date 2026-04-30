import asyncio
from src.tools.finance import _fetch_stock_history
from src.tools.indicators import calculate_macd

def test_cache():
    # 1. Cold fetch
    df1 = _fetch_stock_history("RIVN", "60d", "1d")
    df1.columns = [str(c).lower() for c in df1.columns]
    print("Cold df columns before MACD:", df1.columns)
    df1 = calculate_macd(df1)
    print("Cold df MACD calculated.")

    # 2. Warm fetch
    df2 = _fetch_stock_history("RIVN", "60d", "1d")
    df2.columns = [str(c).lower() for c in df2.columns]
    print("Warm df columns before MACD:", df2.columns)
    df2 = calculate_macd(df2)
    print("Warm df MACD calculated.")

if __name__ == "__main__":
    test_cache()
