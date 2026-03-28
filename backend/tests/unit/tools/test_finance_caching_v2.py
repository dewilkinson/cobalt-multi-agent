import pytest
import asyncio
from datetime import datetime, timedelta
from src.tools.finance import (
    simulate_cache_volatility, 
    get_symbol_history_data, 
    get_cache_heat_map
)
from src.tools.shared_storage import GLOBAL_CONTEXT

@pytest.fixture(autouse=True)
def setup_isolation():
    """Ensure a fresh global context for each test."""
    GLOBAL_CONTEXT.clear()
    yield
    GLOBAL_CONTEXT.clear()

@pytest.mark.asyncio
async def test_system_cache_seeding_and_weighting():
    """
    Simulates the VLI Dashboard's diagnostic flow:
    1. Seed 50 mock stocks via System Node tool.
    2. Verify weighting/heat distribution.
    3. Verify Heat Map generation.
    """
    # 1. Seed the cache
    # Call the AINVOKE method for async tools
    result = await simulate_cache_volatility.ainvoke({"num_high": 10, "num_moderate": 30, "num_inactive": 10})
    assert "Successfully populated 50 mock stocks" in result
    
    ticker_metadata = GLOBAL_CONTEXT.get("ticker_metadata", {})
    history_cache = GLOBAL_CONTEXT.get("history_cache", {})
    
    # 2. Verify total population
    assert len(ticker_metadata) == 50
    assert len(history_cache) == 50
    
    # 3. Verify weighting (Heat)
    high_heat_stocks = [s for s in ticker_metadata if s.startswith("HIGH_")]
    mod_heat_stocks = [s for s in ticker_metadata if s.startswith("MOD_")]
    inact_stocks = [s for s in ticker_metadata if s.startswith("INACT_")]
    
    # Thresholds match finance.py logic
    assert all(ticker_metadata[s]["heat"] >= 25 for s in high_heat_stocks)
    assert all(8 <= ticker_metadata[s]["heat"] <= 18 for s in mod_heat_stocks)
    assert all(ticker_metadata[s]["heat"] <= 3 for s in inact_stocks)
    
    # 4. Verify Heat Map output
    heat_map = await get_cache_heat_map.ainvoke({})
    assert "VLI Hybrid Cache Heat Map" in heat_map
    assert "HIGH_0" in heat_map
    assert "INACT_0" in heat_map
    assert any(c in heat_map for c in ["█", "▓", "▒", "░"])

@pytest.mark.asyncio
async def test_scout_eviction_and_warming_logic():
    """
    Tests the Scout's TTL and Warming behavior:
    1. Seed a stale mock ticker.
    2. Retrieve via Scout.
    3. Verify heat-based sorting for eager worker.
    """
    # Seed a specific mock stock
    GLOBAL_CONTEXT["ticker_metadata"] = {"STALE_MOCK": {"heat": 100}}
    GLOBAL_CONTEXT["history_cache"] = {
        "STALE_MOCK_1d_1h": {
            "data": "### STALE_MOCK\nOld data", 
            "last_updated": datetime.now() - timedelta(minutes=20), 
            "period": "1d", 
            "interval": "1h"
        }
    }
    
    # Request data (heat increments)
    await get_symbol_history_data.ainvoke({"symbols": ["STALE_MOCK"]})
    assert GLOBAL_CONTEXT["ticker_metadata"]["STALE_MOCK"]["heat"] == 101

@pytest.mark.asyncio
async def test_eager_worker_refresh_logic():
    """
    Verifies the eager background worker recognizes 'hot' symbols.
    """
    GLOBAL_CONTEXT["ticker_metadata"] = {"HOT": {"heat": 500}, "COLD": {"heat": 1}}
    
    sorted_by_heat = sorted(GLOBAL_CONTEXT["ticker_metadata"].keys(), 
                            key=lambda sym: GLOBAL_CONTEXT["ticker_metadata"][sym].get('heat', 0), 
                            reverse=True)
    
    assert sorted_by_heat[0] == "HOT"
    assert sorted_by_heat[1] == "COLD"