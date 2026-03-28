import pytest
from unittest.mock import patch, MagicMock

from src.graph.nodes.coordinator import coordinator_node
from src.tools.shared_storage import GLOBAL_CONTEXT

@pytest.fixture(autouse=True)
def clean_global_context():
    """Ensure GLOBAL_CONTEXT is clean before each test."""
    GLOBAL_CONTEXT.clear()
    yield
    GLOBAL_CONTEXT.clear()

def test_coordinator_cache_injection_empty():
    """Verify coordinator injects 'None (Data Store Empty)' when cache is empty."""
    mock_state = {"messages": []}
    mock_config = MagicMock()
    
    with patch("src.graph.nodes.coordinator.apply_prompt_template") as mock_apply:
        mock_apply.return_value = "Mocked output"
        coordinator_node(mock_state, mock_config)
        
        args, _ = mock_apply.call_args
        state_passed = args[1]
        assert state_passed["CACHED_TICKERS"] == "None (Data Store Empty)"

def test_coordinator_cache_injection_populated():
    """Verify coordinator injects sorted, comma-separated tickers when cache is populated."""
    GLOBAL_CONTEXT["cached_tickers"] = {"NVDA", "AMD"}
    
    mock_state = {"messages": []}
    mock_config = MagicMock()
    
    with patch("src.graph.nodes.coordinator.apply_prompt_template") as mock_apply:
        mock_apply.return_value = "Mocked output"
        coordinator_node(mock_state, mock_config)
        
        args, _ = mock_apply.call_args
        state_passed = args[1]
        assert state_passed["CACHED_TICKERS"] == "AMD, NVDA"
