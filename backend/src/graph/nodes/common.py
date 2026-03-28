# Core: Common - Shared node utilities and execution logic.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from src.agents import create_agent_from_registry
from src.config.configuration import Configuration
from src.tools import (
    get_stock_quote,
    get_web_search_tool,
    crawl_tool,
    snapper
)

logger = logging.getLogger(__name__)

async def _setup_and_execute_agent_step(state, config, agent_type, tools, agent_instructions: str = ""):
    """Executes the agent and captures the result for the reporter."""
    
    # 1. Diagnostic Trace: Emit a lifecycle log for the dashboard if in Test Mode
    if state.get("test_mode"):
        from langchain_core.messages import AIMessage
        state["messages"].append(AIMessage(
            content=f"🚀 Node activated: {agent_type.upper()}. Preparing for high-fidelity execution...",
            name=agent_type
        ))

    agent = create_agent_from_registry(agent_type, tools)
    
    # Engagement with the actual agent context
    result = await agent.ainvoke(state, config)
    
    # Extract observations for the dashboard
    observations = []
    last_content = ""
    if isinstance(result, dict) and "messages" in result:
        last_msg = result["messages"][-1]
        if hasattr(last_msg, "content"):
            last_content = last_msg.content
            observations.append(last_content)
    
    # Handle multi-step plan updates
    current_plan = state.get("current_plan")
    goto_node = "reporter"
    
    if current_plan:
        steps = []
        if hasattr(current_plan, "steps"):
            steps = current_plan.steps
        elif isinstance(current_plan, dict) and "steps" in current_plan:
            steps = current_plan["steps"]
            
        for step in steps:
            # Handle both object and dict steps
            if hasattr(step, "execution_res"):
                if getattr(step, "execution_res") is None:
                    setattr(step, "execution_res", last_content or "Executed.")
                    break
            elif isinstance(step, dict) and step.get("execution_res") is None:
                step["execution_res"] = last_content or "Executed."
                break
        
        # Check if more steps remain
        has_more_steps = False
        for step in steps:
            if hasattr(step, "execution_res"):
                if getattr(step, "execution_res") is None:
                    has_more_steps = True
                    break
            elif isinstance(step, dict) and step.get("execution_res") is None:
                has_more_steps = True
                break
                
        if has_more_steps:
            goto_node = "human_feedback"

    return Command(
        update={
            "messages": result.get("messages", []),
            "observations": observations,
            "current_plan": current_plan
        },
        goto=goto_node
    )

# Orchestrator Fast Bypass Tools
def get_orchestrator_tools(config: RunnableConfig):
    """Returns a list of tools available to the Orchestrator for fast bypass."""
    configurable = Configuration.from_runnable_config(config)
    return [
        get_stock_quote,
        get_web_search_tool(configurable.max_search_results),
        crawl_tool,
        snapper
    ]
