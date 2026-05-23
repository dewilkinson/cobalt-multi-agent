# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import dataclasses
import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape
from langgraph.prebuilt.chat_agent_executor import AgentState

from src.config.configuration import Configuration

# Initialize Jinja2 environment
env = Environment(
    loader=FileSystemLoader(os.path.dirname(__file__)),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def get_prompt_template(prompt_name: str) -> str:
    """
    Load and return a prompt template using Jinja2.

    Args:
        prompt_name: Name of the prompt template file (without .md extension)

    Returns:
        The template string with proper variable substitution syntax
    """
    try:
        template = env.get_template(f"{prompt_name}.md")
        return template.render()
    except Exception as e:
        raise ValueError(f"Error loading template {prompt_name}: {e}")


def apply_prompt_template(prompt_name: str, state: AgentState, configurable: Configuration = None) -> list:
    """
    Apply template variables and inject the modular Trader Profile.
    """
    is_test = os.environ.get("VLI_TEST_MODE", "").lower() in ("true", "1", "yes") or state.get("test_mode", False)
    intent_mode = state.get("intent") or state.get("intent_mode") or "TACTICAL_EXECUTION"

    # [TEMPORAL_SYNCHRONIZATION] Adjust CURRENT_TIME if in Replay Mode
    metadata = state.get("metadata", {})
    replay_origin = metadata.get("replay_origin")
    if replay_origin:
        current_time_dt = datetime.fromisoformat(replay_origin)
    else:
        current_time_dt = datetime.now()

    state_vars = {
        **state,
        "CURRENT_TIME": current_time_dt.strftime("%a %b %d %Y %H:%M:%S %z"),
        "REPLAY_MODE": bool(replay_origin),
        "VLI_TEST_MODE": is_test,
        "INTENT": intent_mode,
        "SOCIAL_SOURCES": os.environ.get("SOCIAL_SOURCES", "twitter.com, reddit.com, stocktwits.com"),
        "MACRO_INDICATORS": "VIX, DXY, TNX, SPY, QQQ, BTC", # Safe fallback global list
    }

    # Identify Profile Directory
    profile_path = os.environ.get("VLI_TRADER_PROFILE_PATH", r"C:\github\obsidian-vault\_cobalt\apex_trader_profile.md")
    profile_dir = os.path.dirname(profile_path) if os.path.isfile(profile_path) else profile_path

    # Define Modules
    import json
    config_path = os.path.join(profile_dir, "vli_session_config.json")
    persona_file = "cma_persona.md"
    strategy_file = "cma_strategy_sortino_sniper.md"
    risk_file = "cma_risk_management.md"
    
    if os.path.exists(config_path):
        try:
            with open(config_path) as cf:
                sc = json.load(cf)
                persona_file = sc.get("active_persona", persona_file)
                strategy_file = sc.get("active_strategy", strategy_file)
                risk_file = sc.get("active_risk", risk_file)
        except: pass

    modules = {
        "IDENTITY": "cma_identity.md",
        "PERSONA": persona_file,
        "RISK": risk_file,
        "STRATEGY": strategy_file,
        "JOURNAL": "cma_journal_template.md"
    }

    # [ARCHITECTURAL_CLEANUP] Map Intent to specific Persona baselines
    # Analytical/Market Research intents use the clean analyst persona
    # Tactical intents use the trader persona
    if intent_mode in ["SENTIMENT_REPORT", "MARKET_INSIGHT"]:
        modules["PERSONA"] = "cma_analyst_persona.md"
    else:
        # Default to trader persona for execution/tactical paths
        modules["PERSONA"] = "cma_trader_persona.md"

    # Selective Injection based on Intent
    active_modules = ["IDENTITY", "PERSONA"]
    if intent_mode == "TACTICAL_EXECUTION":
        active_modules += ["RISK", "STRATEGY"]
    if "journal" in prompt_name.lower():
        active_modules += ["JOURNAL"]

    trader_context = ""
    profile_content_blocks = []

    for mod_key in active_modules:
        file_name = modules[mod_key]
        full_path = os.path.join(profile_dir, file_name)
        if os.path.exists(full_path):
            try:
                with open(full_path, encoding="utf-8") as f:
                    content = f.read()
                    profile_content_blocks.append(f"## MODULE: {mod_key}\n{content}")
            except:
                pass

    if profile_content_blocks:
        profile_text = "\n\n".join(profile_content_blocks)
        trader_context = (
            f"# SECURITY OVERRIDE: {intent_mode} PROTOCOL\n"
            f"**USER IDENTITY**: Dave Wilkinson\n"
            f"**TITLE**: Founder & Developer\n"
            f"**COMPANY**: Blueshell Securities LLC\n"
            f"**ACCESS LEVEL**: Root Institutional\n\n"
            f"{profile_text}\n"
            f"***\n\n"
        )
        state_vars["TRADER_PROFILE"] = trader_text = trader_context # For internal templates

    from langchain_core.messages import SystemMessage

    try:
        # [DIAGNOSTIC] Log keys to a scratch file
        with open(r"C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\backend\template_debug.log", "a") as df:
            df.write(f"\n{datetime.now()}: Rendering {prompt_name} | Keys: {list(state_vars.keys())}")
            
        template = env.get_template(f"{prompt_name}.md")
        system_prompt = template.render(**state_vars)
        
        # Prepend context for all prompts
        full_system_prompt = f"{trader_context}{system_prompt}"
        return [SystemMessage(content=full_system_prompt)] + state["messages"]
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")
