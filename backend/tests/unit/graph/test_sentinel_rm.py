# Tests for the Sentinel RM Agent Node
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import HumanMessage
from src.graph.nodes.sentinel_rm import sentinel_rm_node
from src.graph.types import State, Plan

@pytest.mark.asyncio
async def test_sentinel_rm_node_initialization():
    # We aren't testing the full LLM graph execution here, just verifying the 
    # node is importable and conforms to the signature
    assert callable(sentinel_rm_node)

@pytest.mark.asyncio
async def test_sentinel_node_verbosity_and_execution():
    """Test that the Sentinel RM node correctly executes with verbosity controls."""
    with patch("src.graph.nodes.sentinel_rm._setup_and_execute_agent_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {"messages": [HumanMessage(content="Sentinel evaluation complete. [LIQUIDATE]")]}

        state = State(
            current_plan=Plan(
                title="Risk Evaluation",
                thought="",
                steps=[],
                direct_response="",
                locale="en-US",
                has_enough_context=False
            ),
            research_topic="Test Subject",
            verbosity=3
        )
        
        config = MagicMock()
        result = await sentinel_rm_node(state, config)
        
        # Verify result structure output matches expected
        assert "messages" in result
        
        # Verify _setup_and_execute_agent_step was called, verify kwargs
        mock_exec.assert_called_once()
        args, kwargs = mock_exec.call_args
        
        # Check that specific tools are present in the tools payload
        tools = args[3]
        tool_names = [getattr(t, 'name', getattr(t, '__name__', str(t))) for t in tools]
        assert "fetch_market_macros" in tool_names
        assert "get_sortino_ratio" in tool_names
        assert "get_volume_profile" in tool_names
        
        # Verify verbosity instructions
        assert "verbosity=3" in kwargs.get("agent_instructions", "")

def test_sentinel_apex_parenthesis_formatting():
    """Manually test formatting logic strictly mandated by the apex 500 prompt."""
    val = -1500
    formatted = f"({abs(val):,})" if val < 0 else str(val)
    assert formatted == "(1,500)"

    val2 = -300
    formatted2 = f"({abs(val2)})" if val2 < 0 else str(val2)
    assert formatted2 == "(300)"
