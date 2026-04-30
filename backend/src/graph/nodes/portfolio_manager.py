# Agent: Portfolio Manager - Node definition for Strategic Oversight.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.tools import fetch_market_macros, get_portfolio_balance_report, get_smc_analysis, get_stock_quote, update_portfolio_ledger, update_watchlist, get_attribution_summary
from src.tools.broker import sync_brokerage_portfolio, export_to_tradezella
from src.tools.shared_storage import GLOBAL_CONTEXT, PORTFOLIO_MANAGER_CONTEXT

from ..types import State
from .common_vli import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# Portfolio Manager - Overseer of the 'War Barbell' (Shield vs Sword)
# 1. Private context: Local memory for the Portfolio Manager node
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = PORTFOLIO_MANAGER_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


async def portfolio_manager_node(state: State, config: RunnableConfig):
    """Portfolio Manager node implementation for strategic balance and watchlist oversight."""
    logger.info("Portfolio Manager Node: Evaluating War Barbell balance and Watchlist integrity.")

    # Selection of tools for the Overseer
    tools = [get_portfolio_balance_report, update_watchlist, update_portfolio_ledger, get_stock_quote, get_smc_analysis, fetch_market_macros, get_attribution_summary, sync_brokerage_portfolio, export_to_tradezella]

    # Enforce objective reporting
    instructions = f"Report verbosity={state.get('verbosity', 1)}. "
    instructions += "Your first priority is to run 'sync_brokerage_portfolio' to pull real-time SnapTrade data (positions, open orders, filled orders) from Fidelity into your Portfolio Ledger database. "
    instructions += "After syncing, your focus is the 'War Barbell' balance. Categorize all candidates as either 'Sword' (Tech/Growth) or 'Shield' (Energy/Defensive)."

    return await _setup_and_execute_agent_step(state, config, "portfolio_manager", tools, agent_instructions=instructions)
