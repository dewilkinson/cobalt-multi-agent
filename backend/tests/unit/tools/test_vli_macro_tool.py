import asyncio
import pytest
import os
import json
import pandas as pd
from unittest.mock import patch, MagicMock
from src.tools.finance import get_macro_symbols

@pytest.mark.asyncio
@patch("src.tools.finance._fetch_batch_history")
@patch("src.tools.finance._extract_ticker_data")
@patch("src.config.vli.get_vli_path")
async def test_get_macro_stocks_execution(mock_vli_path, mock_extract, mock_fetch):
    """Verifies that the macro tool executes using mocked data."""
    # 1. Redirect VLI transit path to a temp directory
    def side_effect_vli_path(subpath=""):
        return os.path.join("data", "artifacts", "temp_transit", subpath)
    mock_vli_path.side_effect = side_effect_vli_path

    # 2. Mock the batch fetch to return anything non-empty
    mock_fetch.return_value = pd.DataFrame({"dummy": [1, 2]})
    
    # 3. Mock the extractor to return a valid 1000-row dataframe with DatetimeIndex for any ticker
    def mock_extract_fn(df, ticker):
        dates = pd.date_range(end=pd.Timestamp.now(), periods=1000, freq="1min")
        return pd.DataFrame({
            "Close": [400.0] * 999 + [410.0],
            "Volume": [1000] * 1000
        }, index=dates)
    mock_extract.side_effect = mock_extract_fn

    # 4. Run the tool
    result = await get_macro_symbols.ainvoke({})
    
    # 5. Check result content (New JSON format)
    assert '"type": "table"' in result
    assert '"Asset", "Ticker", "Price"' in result
    
    # 6. Check artifact generation
    artifact_path = os.path.join("data", "artifacts", "get_macro_symbols.json")
    if os.path.exists(artifact_path):
        with open(artifact_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Verify the artifact is populated
            assert len(data) > 0
            # Check for the new structured sparkline format
            assert "rows" in data
            for row in data["rows"]:
                sparkline_cell = row[5]
                assert sparkline_cell["type"] == "sparkline"
                # Should contain dictionaries with "v" and "is_prev"
                first_point = sparkline_cell["value"][0]
                assert isinstance(first_point, dict)
                assert "v" in first_point
                assert "is_prev" in first_point

if __name__ == "__main__":
    asyncio.run(test_get_macro_stocks_execution())
