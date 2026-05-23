# Core: Common VLI - Shared node utilities and execution logic (V2 - Cache Buster).
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import logging
import time
import traceback
from datetime import datetime

from langchain_core.messages import AIMessage, SystemMessage
from src.llms.llm import get_llm_by_type
from langchain_core.runnables import RunnableConfig
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from src.agents import create_agent_from_registry
from src.config.configuration import Configuration
from src.tools import crawl_tool, get_stock_quote, get_web_search_tool, invalidate_market_cache, snapper
from src.tools.artifacts import read_session_artifact
from src.config.vli import get_vli_path
from src.utils.vli_metrics import log_vli_metric
from src.config.agents import AGENT_LLM_MAP
from src.utils.temporal import set_reference_time

logger = logging.getLogger(__name__)

# [TIER_CONSTANTS] Global list of Gemini tiers for execution
TIERS = ["reasoning", "basic", "legacy"]


async def _run_node_with_tiered_fallback(agent_type, state, config, tools=None, is_structured=False, structured_schema=None, messages=None):
    """Universal tiered fallback executor for all VLI nodes."""
    current_tier = AGENT_LLM_MAP.get(agent_type, "basic")
    
    # [NEW] Check for forced basic mode via Thinking Toggle
    thinking_mode = state.get("thinking_mode", False) if isinstance(state, dict) else getattr(state, "thinking_mode", False)
    if not thinking_mode and config and config.get("configurable"):
        thinking_mode = config["configurable"].get("thinking_mode", False)
        
    if not thinking_mode:
        current_tier = "basic"
        
    try:
        start_idx = TIERS.index(current_tier)
    except ValueError:
        start_idx = 1
        
    fallback_messages = []
    result = None

    # [REPLAY_INSTRUMENTATION] Re-initialize Temporal Context for the specialist node
    _instrument_temporal_context(state)

    for i in range(start_idx, len(TIERS)):
        tier = TIERS[i]
        
        # Re-initialize based on tier
        is_graph = False
        if tools:
            if is_structured and structured_schema:
                llm = get_llm_by_type(tier)
                runnable = llm.bind_tools(tools).with_structured_output(structured_schema)
            else:
                runnable = create_agent_from_registry(agent_type, tools, override_tier=tier)
                is_graph = True
        else:
            runnable = get_llm_by_type(tier)
            if is_structured and structured_schema:
                runnable = runnable.with_structured_output(structured_schema)

        # Execution
        t0 = time.time()
        
        # [DYNAMIC BUDGET] Calculate remaining global time relative to 300s server limit
        configurable = config.get("configurable", {})
        execution_start_time = configurable.get("execution_start_time", t0)
        elapsed_global = time.time() - execution_start_time
        remaining_global = 290.0 - elapsed_global # Use 290s to leave buffer for 300s master limit
        
        tier_timeouts = {
            "reasoning": 240.0,
            "basic": 180.0,
            "legacy": 120.0
        }
        
        # [ADAPTIVE SKIP] If reasoning is requested but we have < 30s left, skip to basic
        if tier == "reasoning" and remaining_global < 30.0:
            logger.warning(f"[BUDGET_ENFORCEMENT] Skipping Reasoning tier (Remaining: {remaining_global:.1f}s < 30s).")
            # Inject Adaptive Verbosity logic into the prompt history for the fallback model
            if messages is not None:
                if is_structured:
                    # For structured output (like Phase B Coordinator), avoid narrative instructions which break JSON parsing
                    messages.append(SystemMessage(content="[BUDGET_CONSTRAINED]: Maintain valid JSON Plan output, but ensure the 'thought' and 'description' fields are highly detailed."))
                else:
                    # For text/graph nodes (Synthesizer, Reporter), go full depth
                    messages.append(SystemMessage(content="[BUDGET_RECOVERY_MODE]: You have been promoted to the immediate execution tier due to time constraints. You MUST provide a full, high-fidelity institutional answer immediately. Do NOT sacrifice depth for brevity."))
            continue
            
        # Hard-cap the tier timeout by the remaining global budget
        static_timeout = tier_timeouts.get(tier, 150.0)
        tier_timeout = min(static_timeout, max(30.0, remaining_global))
        
        # [TRACE] High-fidelity diagnostic probe
        # [HARDENING] We avoid str(state) or str(messages) here as they are extremely expensive
        # and block the event loop in bloated threads.
        msg_list = messages if messages is not None else state.get("messages", [])
        msgs_count = len(msg_list) if msg_list else 0
        
        # [VISUALIZATION] Determine optimal tier and color code model name
        try:
            temp_llm = get_llm_by_type(tier)
            model_name = getattr(temp_llm, "model", getattr(temp_llm, "model_name", "unknown"))
        except Exception:
            model_name = "unknown"
            
        optimal_tier = AGENT_LLM_MAP.get(agent_type, "basic")
        if tier == optimal_tier:
            colored_model = f"\033[92m[{model_name}]\033[0m" # Green
        else:
            colored_model = f"\033[33m[{model_name}]\033[0m" # Orange
            
        logger.info(f"[TRACE_START] Tier: {tier} {colored_model} | Agent: {agent_type} | Message Count: {msgs_count} | Timeout: {tier_timeout:.1f}s (Global Remaining: {remaining_global:.1f}s)")
        
        try:
            # Determine appropriate input format based on whether we are calling a graph or a raw LLM
            if messages is not None:
                llm_input = {"messages": messages} if is_graph else messages
            else:
                # If messages is None, specialists (graphs) need the whole state, 
                # but raw ChatModels need just the message list.
                llm_input = state if is_graph else state.get("messages", [])
            
            # Execute invocation (result is an AIMessage, State dict, or Structured Pydantic object)
            result = await asyncio.wait_for(runnable.ainvoke(llm_input), timeout=tier_timeout)
            
            # [STABILITY] Null-safety guard for Pydantic/LangChain validation
            if result is None:
                logger.warning(f"[VLI_STABILITY] Tier {tier} returned None. Defaulting to empty AIMessage.")
                result = AIMessage(content="", name="vli_null_recovery")
            else:
                # Force content to be a non-null string
                if hasattr(result, "content") and result.content is None:
                    result.content = ""

            # [PROMPT LEAKAGE GUARD] Detect if the model is echoing its own instructions/security protocol
            res_str = str(result).upper()
            if hasattr(result, "content") and result.content:
                res_str += " " + str(result.content).upper()
            leak_keywords = ["# SECURITY OVERRIDE", "[APEX 500 SYSTEM]", "[SYSTEM INSTRUCTION]", "[USER OVERRIDE DIRECTIVE]", "[OPERATIONAL MANDATE]"]
            is_leak = False
            for x in leak_keywords:
                if x in res_str:
                    logger.warning(f"[LEAK_DEBUG] Detected keyword '{x}' in response context.")
                    is_leak = True
                    break
            
            # Deep check for list of messages
            if not is_leak and isinstance(result, list):
                for item in result:
                    for x in leak_keywords:
                        if x in str(item).upper():
                            logger.warning(f"[LEAK_DEBUG] Detected keyword '{x}' in message item.")
                            is_leak = True
                            break
                    if is_leak:
                        break
            
            duration = time.time() - t0
            logger.info(f"[TRACE_END] Tier: {tier} | Status: {'LEAK' if is_leak else 'OK'} | Duration: {duration:.2f}s")
            
            if (is_structured and isinstance(result, list)) or is_leak:
                if i < len(TIERS) - 1:
                    next_tier = TIERS[i+1]
                    msg = f"STRUCTURAL_EXCEPTION: Integrity check failed on {tier} (Instruction Leak). Falling back to {next_tier}..."
                    fallback_messages.append(AIMessage(content=str(msg), name="system_fallback"))
                    continue
                else:
                    raise TypeError(f"Agent Intelligence Failure: Structural validation failed on all tiers.")
                
            logger.info(f"[TIMING] Tier {tier} ({agent_type}) finished in {time.time() - t0:.2f}s.")
            if hasattr(result, "additional_kwargs"):
                result.additional_kwargs["duration_secs"] = time.time() - t0
            return result, fallback_messages
        except Exception as e:
            if isinstance(e, asyncio.TimeoutError):
                logger.error(f"[VLI_TIER_FAIL] Tier {tier} timed out after {tier_timeout:.2f}s")
                fallback_messages.append(SystemMessage(content=f"[TIER_{tier.upper()}_TIMEOUT] Try a fallback reasoning strategy."))
                
                # [NEW] Telemetry Injection for Visibility
                try:
                    telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
                    timestamp = datetime.now().strftime("[%H:%M:%S]")
                    with open(telemetry_file, "a", encoding="utf-8") as tf:
                        tf.write(f"\n{timestamp} **TIER_STALL:** Tier `{tier.upper()}` timed out ({tier_timeout}s). Rotating to next availability.\n")
                        tf.flush()
                except:
                    pass
            else:
                logger.error(f"[VLI_TIER_FAIL] Tier {tier} failed after {time.time() - t0:.2f}s: {e}")
                logger.error("".join(traceback.format_tb(e.__traceback__)))
                fallback_messages.append(SystemMessage(content=f"[TIER_{tier.upper()}_FAILURE] Error: {e}. Adjust approach and try fallback tier."))
            
            e_str = (str(e) + " " + e.__class__.__name__).upper()
            is_quota = any(x in e_str for x in ["RESOURCE_EXHAUSTED", "429", "QUOTA_EXHAUSTED", "RATE_LIMIT"])
            
            if is_quota:
                fail_msg = f"QUOTA_EXHAUSTED: Quota limit reached for tier {tier}."
                logger.warning(fail_msg)
                
                if i < len(TIERS) - 1:
                    logger.info(f"[VLI_FALLBACK] Quota exhausted for tier {tier}. Rotating to next availability...")
                    continue # Fallback to next tier
                
                if is_structured and structured_schema:
                    try:
                        error_res = structured_schema(
                            locale="en-US",
                            thought=fail_msg,
                            has_enough_context=True,
                            direct_response=fail_msg,
                            title="Quota Failure",
                            steps=[]
                        )
                    except Exception:
                        error_res = {"thought": fail_msg, "has_enough_context": True, "direct_response": fail_msg, "title": "Quota Failure", "steps": []}
                else:
                    error_res = AIMessage(content=fail_msg, name="system_fallback_error")
                
                return error_res, fallback_messages
            else:
                if i < len(TIERS) - 1:
                    continue # Fallback to next tier
                else:
                    # [RELIABILITY] Final tier failure sentinel
                    if isinstance(e, asyncio.TimeoutError):
                        fail_msg = f"VLI System Alert: Agent `{agent_type}` exhausted all LLM tiers due to network timeouts."
                        logger.error(fail_msg)
                        if is_structured and structured_schema:
                            try:
                                return structured_schema(locale="en-US", thought=fail_msg, has_enough_context=False, direct_response=fail_msg, title="Timeout Failure", steps=[]), fallback_messages
                            except Exception:
                                return {"thought": fail_msg, "has_enough_context": False, "direct_response": fail_msg, "title": "Timeout Failure", "steps": []}, fallback_messages
                        else:
                            return AIMessage(content=fail_msg, name="system_timeout_error"), fallback_messages
                    raise e
    return result, fallback_messages


async def _setup_and_execute_agent_step(state, config, agent_type, tools, agent_instructions: str = ""):
    """Executes the agent and captures the result for the reporter with multi-tier fallback."""
    logger.info(f" Specialist `{agent_type.upper()}` is now executing `{agent_instructions[:50]}...` (Tiered Fallback Active).")

    audit_start = datetime.now()
    try:
        result, fallback_messages = await _run_node_with_tiered_fallback(agent_type, state, config, tools=tools)
        latency = (datetime.now() - audit_start).total_seconds()
        from src.config.agents import AGENT_LLM_MAP
        log_vli_metric(agent_type, latency, status="pass", metadata={"tier": AGENT_LLM_MAP[agent_type]})
    except Exception as e:
        latency = (datetime.now() - audit_start).total_seconds()
        log_vli_metric(agent_type, latency, status="fail", metadata={"error": str(e)})
        logger.error(f"Agent `{agent_type}` failed after tiered fallback: {e}")
        raise e

    # Extract observations for the dashboard
    observations = []
    last_content = ""
    if isinstance(result, dict) and "messages" in result:
        last_msg = result["messages"][-1]
        if hasattr(last_msg, "content"):
            last_content = str(last_msg.content)
            observations.append(last_content)

    # Handle multi-step plan updates
    current_plan = state.get("current_plan")
    
    if current_plan:
        steps = []
        if hasattr(current_plan, "steps"):
            steps = current_plan.steps
        elif isinstance(current_plan, dict) and "steps" in current_plan:
            steps = current_plan["steps"]

        for step in steps:
            if hasattr(step, "execution_res"):
                if getattr(step, "execution_res") is None:
                    setattr(step, "execution_res", last_content or "Executed.")
                    break
            elif isinstance(step, dict) and step.get("execution_res") is None:
                step["execution_res"] = last_content or "Executed."
                break

    # Ensure all messages from the agent are "Signed" and properly extracted
    if isinstance(result, dict) and "messages" in result:
        original_len = len(state.get("messages", []))
        new_messages = result["messages"][original_len:]
    elif hasattr(result, "content"):
        new_messages = [result]
    else:
        new_messages = []

    if not new_messages:
        new_messages = [AIMessage(content=f"{agent_type.upper()} task completed successfully.", name=f"{agent_type}_finalize")]
    else:
        last_msg = new_messages[-1]
        content_val = last_msg.content if hasattr(last_msg, "content") else last_msg
        
        if (isinstance(content_val, (dict, list))) and not isinstance(content_val, list):
             import json
             content_str = f"```json\n{json.dumps(content_val, indent=2)}\n```"
        elif isinstance(content_val, list):
             content_parts = []
             # [FIX] Do not iterate over a list if it's actually a list of single characters
             if all(isinstance(c, str) and len(c) == 1 for c in content_val):
                 content_str = "".join(content_val)
             else:
                 for item in content_val:
                     if isinstance(item, dict) and "text" in item:
                         content_parts.append(str(item["text"]))
                     else:
                         content_parts.append(str(item))
                 content_str = "\n".join(content_parts)
        else:
             content_str = str(content_val)
        # Preserve telemetry metadata for dashboard token tracking
        new_kwargs = {}
        if hasattr(last_msg, "usage_metadata") and last_msg.usage_metadata:
            new_kwargs["usage_metadata"] = last_msg.usage_metadata
        if hasattr(last_msg, "response_metadata") and last_msg.response_metadata:
            new_kwargs["response_metadata"] = last_msg.response_metadata
            
        new_messages[-1] = AIMessage(content=content_str, name=f"{agent_type}_finalize", **new_kwargs)
    # [SILENT_MODE] Suppression prefix for UI
    if state.get("silent_mode"):
        for m in new_messages:
            if hasattr(m, "content"):
                m.content = f"[SILENT_LOG] {m.content}"

    return {"messages": fallback_messages + new_messages, "observations": observations, "current_plan": current_plan}


def _compact_history(messages: list) -> list:
    """
    Compacts message history for synthesis.
    Filters out structural planning messages to provide a clean context for the reporter.
    """
    compacted = []
    # Nodes whose messages should be ignored in final narrative synthesis EXCEPT when they hold result logic
    # [V3 HARDENING] We only skip purely structural metadata nodes
    structural_nodes = ["vli_spine", "vli_parser", "vli_coordinator", "parser"]
    
    # [HARDENING] Specialist findings MUST be preserved
    specialist_nodes = ["smc_analyst", "analyst", "portfolio_manager", "risk_manager", "coder", "journaler", "synthesizer"]
    
    for m in messages:
        name = getattr(m, "name", "") or ""
        
        # 1. Skip strictly structural nodes unless they are the final message
        if name in structural_nodes and m != messages[-1]:
            continue
            
        # 2. Skip 'coordinator' if it's just a planning stage and NOT a finalization
        if "coordinator" in name:
            content = str(getattr(m, "content", ""))
            # If it's the very last message in the set, we must keep it (it's the answer)
            if m == messages[-1]:
                 pass # Keep
            # If it looks like a planning object (contains internal braces or keys), skip it
            elif "{" in content and "steps" in content:
                 continue
            
        compacted.append(m)
    return compacted


# Orchestrator Fast Bypass Tools
def get_orchestrator_tools(config: RunnableConfig):
    """Returns a list of tools available to the Orchestrator for fast bypass."""
    from src.tools import get_brokerage_accounts, get_brokerage_balance, get_attribution_summary, get_daily_blotter, get_personal_risk_metrics, get_brokerage_statements, fetch_market_macros
    from src.tools.scheduler import manage_scheduled_tasks
    from src.tools.scanner import trigger_manual_analysis_scan, evict_analysis_report, trigger_morning_scan

    configurable = Configuration.from_runnable_config(config)
    return [
        get_stock_quote,
        invalidate_market_cache,
        get_web_search_tool(configurable.max_search_results),
        crawl_tool,
        snapper,
        get_brokerage_accounts,
        get_brokerage_balance,
        get_attribution_summary,
        get_daily_blotter,
        get_personal_risk_metrics,
        get_brokerage_statements,
        fetch_market_macros,
        read_session_artifact,
        manage_scheduled_tasks,
        trigger_manual_analysis_scan,
        evict_analysis_report,
        trigger_morning_scan,
    ]


def _instrument_temporal_context(state: dict):
    """Detects replay origins in the state and re-synchronizes the virtual clock for the current node's context."""
    metadata = state.get("metadata", {})
    replay_origin = metadata.get("replay_origin")
    
    if replay_origin:
        try:
            from datetime import datetime
            origin_dt = datetime.fromisoformat(replay_origin)
            set_reference_time(origin_dt)
            logger.info(f"[VLI_TEMPORAL_SYNC] Specialized node synchronized to: {replay_origin}")
        except Exception as e:
            logger.error(f"[VLI_TEMPORAL_SYNC] Failed to synchronize specialized node: {e}")
