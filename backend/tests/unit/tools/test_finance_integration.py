import pytest
from src.tools.finance import run_smc_analysis
from src.tools.indicators import get_sortino_ratio, get_sharpe_ratio

@pytest.mark.asyncio
async def test_run_smc_analysis():
    # Test valid ticker using ainvoke for StructuredTool
    result = await run_smc_analysis.ainvoke({"ticker": "AAPL"})
    assert isinstance(result, str)
    assert ("Bias" in result or "MTF SMC Alignment" in result)
    
    # Test MTF alignment behavior (it should return formatting indicating support)
    assert "AAPL" in result

@pytest.mark.asyncio
async def test_get_sortino_ratio():
    result = await get_sortino_ratio.ainvoke({"ticker": "AAPL"})
    assert isinstance(result, str)
    assert "Sortino Ratio" in result

@pytest.mark.asyncio
async def test_get_sharpe_ratio():
    result = await get_sharpe_ratio.ainvoke({"ticker": "AAPL"})
    assert isinstance(result, str)
    assert "Sharpe Ratio" in result

@pytest.mark.asyncio
async def test_run_smc_analysis_normalization():
    # Test crypto normalizing from ETHUSDT to ETH-USD
    result = await run_smc_analysis.ainvoke({"ticker": "ETHUSDT"})
    assert isinstance(result, str)
    assert "ETH" in result

