# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

from langgraph.graph import MessagesState
from src.prompts.planner_model import Plan
from src.rag import Resource

class State(MessagesState):
    """Deeply typed state for the multi-agent graph with session persistence."""

    # Runtime Local Variables
    locale: str = "en-US"
    verbosity: int = 1
    research_topic: str = ""
    observations: list[str] = []
    resources: list[Resource] = []
    
    # Planning & Orchestration (Hub-and-Spoke)
    current_plan: Plan | str = None
    steps_completed: int = 0
    is_plan_approved: bool = False
    plan_iterations: int = 0
    
    # Reports & Persistence
    final_report: str = ""
    auto_accepted_plan: bool = False
    enable_background_investigation: bool = True
    background_investigation_results: str = None
    macro_history: str = ""
    portfolio_ledger: str = ""
    active_watchlist: list[str] = []
    obsidian_settings: dict = {}
    gui_overrides: dict = {}
    
    # Simulation & Lifecycle
    test_mode: bool = False
    is_test_mode: bool = False
    direct_mode: bool = False
