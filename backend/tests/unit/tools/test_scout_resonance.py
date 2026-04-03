import pytest
import asyncio
import pandas as pd
from src.tools.finance import _normalize_ticker, _extract_ticker_data

@pytest.mark.asyncio
async def test_scout_ticker_normalization():
    """Verify that VIX and other indices are correctly mapped to their yfinance equivalents."""
    assert _normalize_ticker("VIX") == "^VIX"
    assert _normalize_ticker("SPX") == "^SPX"
    assert _normalize_ticker("AAPL") == "AAPL"

@pytest.mark.asyncio
async def test_scout_extraction_alignment():
    """Verify that extraction works even with the MultiIndex structure returned by batched downloads."""
    # Create a mock MultiIndex DataFrame like yfinance returns for mapped tickers
    cols = pd.MultiIndex.from_tuples([('^VIX', 'Close'), ('^VIX', 'High')])
    df = pd.DataFrame([[30.0, 31.0]], columns=cols)
    
    # Scout asks for 'VIX', but data is under '^VIX'
    extracted = _extract_ticker_data(df, "VIX")
    
    assert not extracted.empty
    assert "Close" in extracted.columns
    assert extracted.iloc[0]['Close'] == 30.0

@pytest.mark.asyncio
async def test_scout_hybrid_resolver_presence():
    """Verify that the tool is correctly configured and has a func attribute."""
    from src.tools.finance import get_stock_quote
    assert hasattr(get_stock_quote, "func")
    assert get_stock_quote.name == "get_stock_quote"

if __name__ == "__main__":
    import sys
    pytest.main([__file__, "-v", "-s"])
