# Agent: Parser - Node definition for initial vibe processing.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any, Literal
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.config.agents import AGENT_LLM_MAP
from src.config.configuration import Configuration
from src.llms.llm import get_llm_by_type
from src.prompts.planner_model import Plan
from src.prompts.template import apply_prompt_template
from src.tools.shared_storage import ORCHESTRATOR_CONTEXT, GLOBAL_CONTEXT
from ..types import State

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = ORCHESTRATOR_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

async def parser_node(state: State, config: RunnableConfig) -> Command[Literal["coordinator", "reporter", "__end__"]]:
    """Parser node (VibeLink Interface) - Initial Input Processor with Fast-Path."""
    logger.info("VLI Parser is processing user vibe.")
    
    from .common_vli import get_orchestrator_tools
    tools = get_orchestrator_tools(config)
    llm = get_llm_by_type(AGENT_LLM_MAP.get("parser", "basic"))
    llm_with_tools = llm.bind_tools(tools)
    
    # 0. Context Horizon Management (TPM Mitigation) with Turn-Aware Slicing
    # Prevent 1M TPM quota hits by truncating history, but ensure we start at a HumanMessage boundary.
    # This prevents Gemini 'INVALID_ARGUMENT' errors caused by orphaned ToolMessages.
    MAX_HISTORY = 10
    raw_messages = state.get("messages", [])
    if len(raw_messages) > MAX_HISTORY:
        # Find the nearest HumanMessage boundary starting from our target slice index
        # We search backwards from the target point to find the most recent 'Reset' point
        target_idx = len(raw_messages) - MAX_HISTORY
        while target_idx > 0 and not isinstance(raw_messages[target_idx], HumanMessage):
            target_idx -= 1
        
        logger.info(f"[VLI_PARSER] Context horizon truncated at index {target_idx} (Starting at HumanMessage).")
        sliced_state = state.copy()
        sliced_state["messages"] = raw_messages[target_idx:]
        messages = apply_prompt_template("parser", sliced_state)
    else:
        messages = apply_prompt_template("parser", state)
    
    # 1. First Pass: Check for direct tool-call shortcuts (Fast-Path)
    # We use a standard invoke first to see if it wants to use tools immediately
    response = await llm_with_tools.ainvoke(messages)
    
    tech_keywords = ["analyze", "analysis", "smc", "sortino", "sharpe", "report"]
    user_query_content = str(raw_messages[-1].content).lower() if raw_messages else ""
    is_technical = any(kw in user_query_content for kw in tech_keywords) and not state.get("direct_mode", False)
    
    if response.tool_calls and not is_technical:
        logger.info(f"[VLI_PARSER] Fast-path triggered with {len(response.tool_calls)} tool calls.")
        from langchain_core.messages import ToolMessage
        
        # 1. Execute the tools in parallel (Bypass redundant Scout LLM loops)
        name_to_tool = {t.name: t for t in tools}
        
        async def invoke_tool(tc):
            t_name = tc["name"]
            t_args = tc["args"]
            if t_name in name_to_tool:
                try:
                    logger.info(f"[VLI_PARSER] Directly invoking tool (Parallel): {t_name}")
                    res = await name_to_tool[t_name].ainvoke(t_args, config)
                    return ToolMessage(content=str(res), tool_call_id=tc["id"], name=t_name)
                except Exception as e:
                    logger.error(f"[VLI_PARSER] Tool execution failed: {e}")
                    return ToolMessage(content=f"Error executing tool: {e}", tool_call_id=tc["id"], name=t_name)
            else:
                return ToolMessage(content=f"Error: Tool {t_name} not found.", tool_call_id=tc["id"], name=t_name)
        
        import asyncio
        tool_results_msgs = list(await asyncio.gather(*[invoke_tool(tc) for tc in response.tool_calls]))
                
        # 2. Extract and synthesize into a colleague-like "Direct Response"
        all_msgs = messages + [response] + tool_results_msgs
        all_msgs.append(HumanMessage(content="Synthesize the above tool results into a clear, professional response, as if you are a skilled colleague giving an update. Use regular English, maintain a helpful tone, but avoid excessive pleasantries, robotic jargon, or overly friendly fawning."))
        
        final_polish = await llm.ainvoke(all_msgs)
        response_text = str(final_polish.content)
        
        # STREAM FIX: Include all intermediate messages from the fast-path
        return Command(
            update={
                "final_report": response_text, 
                "messages": [response] + tool_results_msgs + [AIMessage(content=response_text, name="vli_parser")]
            },
            goto="reporter",
        )

    # 2. Regular Path: If no immediate tool call, generate a structured plan
    structured_llm = llm_with_tools.with_structured_output(Plan)
    plan_obj = structured_llm.invoke(messages)
    
    if plan_obj.has_enough_context or plan_obj.direct_response:
        # [CONTEXT POISONING GUARDRAIL]
        # Prevent the parser from hallucinating a direct response if the user is asking for deep analysis.
        # This occurs if previous Direct Mode mock responses are still in the thread history.
        tech_keywords = ["analyze", "analysis", "smc", "sortino", "sharpe", "report"]
        last_msg_text = str(messages[-1].content).lower() if messages else ""
        if any(kw in last_msg_text for kw in tech_keywords) and not state.get("direct_mode", False):
            logger.warning(f"[VLI_PARSER] Guardrail triggered: Parser attempted to bypass graph for technical query '{last_msg_text}'. Routing to Coordinator.")
            plan_obj.has_enough_context = False
            plan_obj.direct_response = ""
            return Command(
                update={
                    "current_plan": plan_obj,
                    "locale": plan_obj.locale,
                    "research_topic": plan_obj.title,
                },
                goto="coordinator",
            )

        # Improved natural language response for greetings and simple queries
        response_text = plan_obj.direct_response or f"Understood. I have enough context to proceed with your request: {plan_obj.title}."
        
        # GUI OVERRIDE PASS-THROUGH
        update_data = {
            "current_plan": plan_obj,
            "locale": plan_obj.locale,
            "final_report": response_text, 
            "messages": [AIMessage(content=response_text, name="vli_parser")]
        }
        if plan_obj.gui_overrides:
            update_data["gui_overrides"] = plan_obj.gui_overrides
            logger.info(f"[VLI_PARSER] Applying GUI overrides: {plan_obj.gui_overrides}")

        # PERSISTENCE LOGIC: Save Vibe to disk
        if plan_obj.save_gui_vibe:
            import json
            import os
            from src.config.vli import get_gui_vibe_path
            vibe_path = get_gui_vibe_path()
            try:
                existing_vibe = {}
                if os.path.exists(vibe_path):
                    with open(vibe_path, "r", encoding="utf-8") as f:
                        existing_vibe = json.load(f)
                
                # Merge current overrides into existing vibe
                if plan_obj.gui_overrides:
                    existing_vibe.update(plan_obj.gui_overrides)
                
                # Ensure the directory exists
                os.makedirs(os.path.dirname(vibe_path), exist_ok=True)
                
                with open(vibe_path, "w", encoding="utf-8") as f:
                    json.dump(existing_vibe, f, indent=4)
                logger.info(f"[VLI_PARSER] Persisted GUI vibe to {vibe_path}")
            except Exception as e:
                logger.error(f"[VLI_PARSER] Error saving GUI vibe: {e}")

        return Command(
            update=update_data,
            goto="reporter",
        )

    return Command(
        update={
            "current_plan": plan_obj,
            "locale": plan_obj.locale,
            "research_topic": plan_obj.title,
        },
        goto="coordinator",
    )
