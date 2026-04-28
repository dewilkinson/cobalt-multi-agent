# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging

from langgraph.prebuilt import create_react_agent

from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type
from src.prompts import apply_prompt_template

from .registry import registry

logger = logging.getLogger(__name__)


# Create agents using configured LLM types
def create_agent(agent_name: str, agent_type: str, tools: list, prompt_template: str, override_tier: str = None):
    """Factory function to create agents with consistent configuration."""

    # Defensive lookup for LLM tier
    llm_tier = override_tier if override_tier else AGENT_LLM_MAP.get(agent_type, "basic")

    return create_react_agent(
        name=agent_name,
        model=get_llm_by_type(llm_tier),
        tools=tools,
        prompt=lambda state: apply_prompt_template(prompt_template, state),
    )


def create_agent_from_registry(agent_type: str, resolved_tools: list, override_tier: str = None):
    """Creates an agent using configuration from the registry."""
    config = registry.get_agent_config(agent_type)
    if not config:
        logger.error(f"Agent type '{agent_type}' not found in registry. Using default factory.")
        return create_agent(agent_type, agent_type, resolved_tools, agent_type, override_tier=override_tier)

    return create_agent(agent_name=config.get("name", agent_type), agent_type=agent_type, tools=resolved_tools, prompt_template=config.get("prompt_file", agent_type), override_tier=override_tier)
