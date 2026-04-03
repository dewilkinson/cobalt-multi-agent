# Agent: SMC Analyst - Node definition for ICT-based market structure analysis.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

from src.tools.finance import run_smc_analysis, get_stock_quote
from src.tools.indicators import get_volume_profile, get_volatility_atr, get_sharpe_ratio, get_sortino_ratio
from src.tools.shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT
from ..types import State
from .common_vli import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

async def smc_analyst_node(state: State, config: RunnableConfig):
    """
    SMC Analyst node implementation. 
    Specializes in Inner Circle Trader (ICT) concepts: FVG, Order Blocks, BOS, ChoCh.
    """
    cached_list = ", ".join(sorted(list(GLOBAL_CONTEXT.get("cached_tickers", set()))))
    logger.info(f"SMC Analyst Node: Executing ICT Structural Analysis. GLOBAL_CACHE_VISIBILITY=[{cached_list}]")
    
    tools = [
        run_smc_analysis, 
        get_stock_quote, 
        get_volume_profile,
        get_volatility_atr,
        get_sortino_ratio,
        get_sharpe_ratio
    ]

    instructions = (
        "You are a specialized SMC (Smart Money Concepts) and ICT Analyst. "
        "Your goal is to identify institutional market structure. "
        "Always use the 'run_smc_analysis' tool for deep structural data (BOS, ChoCh, FVG, OB). "
        "Explain these concepts to the user in a high-fidelity, institutional tone. "
        "Focus on 'Change of Character' (ChoCh) as a trend-reversal signal and 'Break of Structure' (BOS) as continuation. "
        "Report all identified FVG and Order Blocks as zones of interest. "
        "NOTE: Sortino ratio is the preferred ratio unless Sharpe is explicitly requested. "
        "Do not hallucinate outputs. If a tool fails with an error, gracefully relay the failure."
    )
    
    return await _setup_and_execute_agent_step(
        state, 
        config, 
        "smc_analyst", 
        tools, 
        agent_instructions=instructions
    )
