# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import pytest
from unittest.mock import MagicMock, patch
from src.graph.nodes import analyst_node
from langchain_core.messages import HumanMessage
from src.graph.types import State, Plan

@pytest.mark.asyncio
async def test_analyst_node_verbosity_zero():
    """Test that the Analyst node correctly 'gets' data with verbosity controls."""
    from unittest.mock import AsyncMock
    with patch("src.graph.nodes.analyst._setup_and_execute_agent_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {"messages": [HumanMessage(content="Result without filler")]}

        state = State(
            current_plan=Plan(
                title="Financial modeling",
                thought="Focus heavily on quantitative metrics.",
                steps=[],
                direct_response="",
                locale="en-US",
                has_enough_context=False
            ),
            research_topic="Test Topic",
            verbosity=0
        )
        
        config = MagicMock()
        result = await analyst_node(state, config)
        
        # Verify result structure output matches expected
        assert "messages" in result
        
        # Verify _setup_and_execute_agent_step was called, verify kwargs
        mock_exec.assert_called_once()
        kwargs = mock_exec.call_args[1]
        assert "verbosity=0" in kwargs.get("agent_instructions", "")

@pytest.mark.asyncio
async def test_analyst_restriction():
    """Ensure analyst properly 'gets' internal data and respects restrictions."""
    from unittest.mock import AsyncMock
    with patch("src.graph.nodes.analyst._setup_and_execute_agent_step", new_callable=AsyncMock) as mock_exec:
        state = State(
            current_plan=Plan(
                title="Analysis",
                thought="",
                steps=[],
                direct_response="",
                locale="en-US",
                has_enough_context=False
            ),
            verbosity=1
        )
        config = MagicMock()
        await analyst_node(state, config)
        
        # Verify analyst is given its specific technical primitives
        agent_tools = mock_exec.call_args[0][3]
        tool_names = [getattr(t, "name", getattr(t, "__name__", "")) for t in agent_tools]
        
        # Technical indicators (Math Engine)
        assert "get_smc_analysis" in tool_names
        assert "get_rsi_analysis" in tool_names
        assert "get_bollinger_bands" in tool_names
        
        # External web tools should NOT be here (separation of concerns)
        assert "get_web_search_tool" not in tool_names
        assert "crawl_tool" not in tool_names
        
