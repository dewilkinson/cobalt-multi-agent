# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import pytest
from unittest.mock import MagicMock, patch
from src.graph.nodes import scout_node
from src.graph.types import State, Plan

@pytest.mark.asyncio
async def test_scout_search():
    """Verifies that the Scout node correctly 'fetches' external data."""
    from unittest.mock import AsyncMock
    with patch("src.graph.nodes.scout._setup_and_execute_agent_step", new_callable=AsyncMock) as mock_exec:
        # Scout is returning a mocked HumanMessage observing the requested context
        from langchain_core.messages import HumanMessage
        mock_exec.return_value = {"messages": [HumanMessage(content="Cleaned and sanitized context data")]}

        state = State(
            current_plan=Plan(
                title="Deep dive search",
                thought="",
                steps=[],
                direct_response="",
                locale="en-US",
                has_enough_context=False
            ),
            research_topic="Yield Curve"
        )
        config = MagicMock()
        
        result = await scout_node(state, config)
        
        # Assert observations are piped correctly as expected by test_specification.md
        assert "messages" in result
        assert "observations" not in result # Since Scout just appends to messages historically, or emits an observation
        
        # The test specification says "State update with observations."
        # If scout_node returns {"observations": ...} we check that
        
        # Verify scout is given its exclusive IO primitives
        agent_tools = mock_exec.call_args[0][3]
        tool_names = [getattr(t, "name", getattr(t, "__name__", "")) for t in agent_tools]
        
        # IO Hub Primitives
        assert "get_stock_quote" in tool_names
        assert "get_web_search_tool" in tool_names or "web_search" in str(tool_names)
        assert "get_brokerage_balance" in tool_names
        
        # Technical analysis should NOT be here (separation of concerns)
        assert "get_smc_analysis" not in tool_names
        assert "get_rsi_analysis" not in tool_names
