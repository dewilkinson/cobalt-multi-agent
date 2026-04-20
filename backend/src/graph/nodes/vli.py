# Agent: VLI (VibeLink Interface) - The Central Nervous System
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
import os
import time
import asyncio
import re
from typing import Any, Literal, cast
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langgraph.graph import END

from src.config.agents import AGENT_LLM_MAP
from src.config.analyst import get_analyst_keywords
from src.config.configuration import Configuration
from src.llms.llm import get_llm_by_type
from src.prompts.planner_model import Plan, Step, StepType
from src.prompts.template import apply_prompt_template
from src.tools.shared_storage import GLOBAL_CONTEXT, ORCHESTRATOR_CONTEXT
from src.services.macro_registry import macro_registry
from src.utils.temporal import set_reference_time, parse_temporal_directive

from ..types import State

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = ORCHESTRATOR_CONTEXT

# 2. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


async def vli_node(
    state: State, config: RunnableConfig
) -> Command[
    Literal["portfolio_manager", "smc_analyst", "analyst", "risk_manager", "journaler", "synthesizer", "coder", "imaging", "system", "reporter", "human_feedback", "session_monitor", "vision_specialist", "terminal_specialist", "__end__"]
]:
    """
    Unified VLI Spine Node.
    Handles: Vibe Checking, Fast-Path, Multi-step Planning, and Execution Coordination.
    """
    logger.info("VLI Spine is processing context.")

    # 0. Configuration & Model Selection
    configurable = Configuration.from_runnable_config(config)
    llm_type = "basic"  # [REVERTED] Default to basic (Gemini Flash)
    if hasattr(configurable, "vli_llm_type"):
        llm_type = getattr(configurable, "vli_llm_type")
    elif "vli_llm_type" in config.get("configurable", {}):
        llm_type = config["configurable"]["vli_llm_type"]
    else:
        # Fallback to the explicit registry if the override isn't present
        llm_type = AGENT_LLM_MAP.get("coordinator", "core")

    llm = get_llm_by_type(llm_type)

    # 1. Turn Awareness & Execution Tracking
    current_plan = state.get("current_plan")
    if isinstance(current_plan, dict):
        try:
            current_plan = Plan(**current_plan)
        except Exception as e:
            logger.error(f"[VLI_SPINE] Failed to reconstruct Plan object from dict: {e}")
            # [RECOVERY] Initialize a safe fallback plan to prevent AttributeError downstream
            current_plan = Plan(
                locale="en-US",
                has_enough_context=False,
                thought=f"Reconstruction Failure Recovery: {e}",
                title="System Recovery Plan",
                steps=[]
            )
            
    steps_completed = state.get("steps_completed", 0)
    raw_messages = state.get("messages", [])

    # Layer 0: High-Priority Intent Tracking (Admin/Math/Direct)
    user_query = str(raw_messages[-1].content) if raw_messages else ""
    
    # [HARDENING] Identify the ORIGINAL human query for this turn to prevent intent-drift
    # on multi-node agent execution paths.
    original_human_query = ""
    for msg in reversed(raw_messages):
        if isinstance(msg, (HumanMessage, ToolMessage)): # Use last human input or tool trigger
            if isinstance(msg, HumanMessage):
                original_human_query = str(msg.content)
                break
    
    if not original_human_query:
        original_human_query = user_query

    force_direct_exit = "--direct" in original_human_query.lower()
    
    stripped_query = original_human_query.lower().replace("--direct", "").strip()
    is_admin = any(kw in stripped_query for kw in ["invalidate", "clear cache", "vli tick", "reset diagnostic", "heat map"])
    
    is_arithmetic = bool(re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', stripped_query))
    is_algebra = "solve for" in stripped_query or "calculate" in stripped_query or "=" in stripped_query
    
    # State Synchronization for routing stability
    state_intent = state.get("intent", "")
    is_direct = is_admin or force_direct_exit or (state_intent == "EXECUTE_DIRECT")
    
    if is_arithmetic and not is_algebra and not force_direct_exit:
        try:
            safe_query = re.sub(r'[^0-9\+\-\*\/\(\)\s\.]', '', user_query)
            result = eval(safe_query, {"__builtins__": None}, {})
            logger.info(f"[VLI_SPINE] Layer 0 Math Interceptor triggered: {result}")
            return Command(
                update={
                    "messages": raw_messages + [AIMessage(content=f"Result: {result}", name="math_interceptor")],
                    "intent": "EXECUTE_DIRECT"
                },
                goto=END
            )
        except:
            pass

    # [TEMPORAL_INSTRUMENTATION] Replay Engine Detection
    # Detect if the user is asking about a past timeframe
    temporal_origin = parse_temporal_directive(user_query)
    if temporal_origin:
        logger.info(f"[VLI_SPINE] Temporal shift detected: {temporal_origin.strftime('%Y-%m-%d')}")
        set_reference_time(temporal_origin)
        
        # [SYNCHRONIZATION] Propagate to state for the Planner (Coordinator)
        state["metadata"] = state.get("metadata", {})
        state["metadata"]["replay_origin"] = temporal_origin.isoformat()
        
        # Inject into telemetry for dashboard visibility
        try:
            from src.config.vli import get_vli_path
            telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp} ### 🕰️ [REPLAY_ENGINE_ACTIVE]\n> Origin shifted to: **{temporal_origin.strftime('%Y-%m-%d %H:%M:%S')}**\n> All subsequent analytical samples are relative to this origin.\n")
                tf.flush()
        except:
            pass

    # [COORDINATION LOGIC] Check if returning from a specialist
    if raw_messages:
        last_msg = raw_messages[-1]
        msg_name = getattr(last_msg, "name", None)
        # If msg came from a specialist, increment completion
        if msg_name and msg_name not in ["vli", "vli_spine", "vli_parser", "vli_coordinator", "assistant", "Assistant"]:
            steps_completed += 1
            # If plan is finished, route to reporter (unless direct admin status is required)
            plan_steps = current_plan.steps if isinstance(current_plan, Plan) else current_plan.get("steps", [])
            plan_len = len(plan_steps)
            
            logger.info(f"[VLI_SPINE] Returning from specialist '{msg_name}'. Completion: {steps_completed}/{plan_len}")

            if current_plan and steps_completed >= plan_len:
                logger.info(f"[VLI_SPINE] Plan complete ({steps_completed}/{plan_len}). Routing to termination/synthesis.")
                
                # Use centralized Layer 0 intent detection for consistency
                plan_intent = getattr(current_plan, "intent", "") if isinstance(current_plan, Plan) else current_plan.get("intent", "")
                is_direct_final = is_direct or (plan_intent == "EXECUTE_DIRECT")
                
                logger.info(f"[VLI_SPINE] Final Intent Audit: is_direct={is_direct}, plan_intent={plan_intent}, final={is_direct_final}")
                
                return Command(
                    update={
                        "steps_completed": steps_completed, 
                        "intent": "EXECUTE_DIRECT" if is_direct_final else state_intent,
                        "current_plan": current_plan,
                        "metadata": state.get("metadata", {})
                    }, 
                    goto=END if is_direct_final or state.get("raw_data_mode") else "reporter"
                )
            elif current_plan and steps_completed < plan_len:
                logger.info(f"[VLI_SPINE] Plan in progress ({steps_completed}/{plan_len}). Routing to next step.")
                next_step = plan_steps[steps_completed]
                # Handle dictionary representation of Step or Enum
                next_node = next_step.step_type.value if hasattr(next_step, "step_type") else next_step.get("step_type", "analyst")
                return Command(
                    update={"steps_completed": steps_completed},
                    goto=next_node
                )

    # 2. Workspace & Metadata Synchronization
    analyst_keywords = ", ".join([str(k) for k in get_analyst_keywords()])
    macro_labels = ", ".join([str(k) for k in list(macro_registry.get_macros().keys())])

    # Inject Daily Action Plan from Obsidian
    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if vault_path:
        plan_file = os.path.join(vault_path, "_cobalt", "Daily_Action_Plan.md")
        if os.path.exists(plan_file):
            try:
                with open(plan_file, encoding="utf-8") as f:
                    _GLOBAL_RESOURCE_CONTEXT["daily_action_plan"] = f.read()
            except Exception:
                pass

    # Prepare artifact directory scope
    artifacts_dir = os.path.join(os.getcwd(), "data", "artifacts")
    available_artifacts = ""
    if os.path.exists(artifacts_dir):
        available_artifacts = ", ".join([str(a) for a in os.listdir(artifacts_dir)])

    state_for_prompt = {
        **state,
        "ANALYST_KEYWORDS": analyst_keywords,
        "MACRO_INDICATORS": macro_labels,
        "DAILY_ACTION_PLAN": _GLOBAL_RESOURCE_CONTEXT.get("daily_action_plan", "No daily instructions."),
        "CACHED_TICKERS": ", ".join([str(t) for t in sorted(list(_GLOBAL_RESOURCE_CONTEXT.get("cached_tickers", set())))]) or "None",
        "SYMBOL_ARTIFACTS": str(available_artifacts) if available_artifacts else "None",
    }

    # 3. Context Horizon Management (TPM Mitigation)
    MAX_HISTORY = 12
    if len(raw_messages) > MAX_HISTORY:
        target_idx = len(raw_messages) - MAX_HISTORY
        while target_idx > 0 and not isinstance(raw_messages[target_idx], HumanMessage):
            target_idx -= 1

        # [NEW] Prune message content internally to avoid prompt saturation
        pruned_msgs = []
        for m in raw_messages[target_idx:]:
            content = str(getattr(m, "content", ""))
            if len(content) > 3000:
                # Truncate overly verbose tool results for the Planner's sanity
                content = content[:1500] + "\n... [TRUNCATED FOR PLANNING STABILITY] ...\n" + content[-500:]

            # Reconstruct message with pruned content
            if isinstance(m, HumanMessage):
                pruned_msgs.append(HumanMessage(content=content))
            elif isinstance(m, AIMessage):
                pruned_msgs.append(AIMessage(content=content, name=m.name))
            elif isinstance(m, ToolMessage):
                pruned_msgs.append(ToolMessage(content=content, name=m.name, tool_call_id=m.tool_call_id))
            else:
                pruned_msgs.append(m)

        state_for_prompt["messages"] = pruned_msgs
        logger.info(f"[VLI_SPINE] History pruned and truncated at index {target_idx}")

    # 4. Phase A: Fast-Path & Intent Classification
    from .common_vli import get_orchestrator_tools

    logger.info("[VLI_SPINE] Fetching orchestrator tools...")
    tools = get_orchestrator_tools(config)
    logger.info(f"[VLI_SPINE] Tools loaded: {len(tools)}. Binding to LLM...")
    llm_with_tools = llm.bind_tools(tools)


    messages = apply_prompt_template("parser", state_for_prompt)

    # Heuristic Rule Injection (Institutional Stability)
    core_logic_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "CORE_LOGIC.md")
    if os.path.exists(core_logic_path):
        try:
            with open(core_logic_path, "r", encoding="utf-8") as f:
                rules = [l.strip() for l in f.readlines() if l.strip().startswith(("-", "*"))]
                if rules:
                    messages.append(HumanMessage(content="[INSTITUTIONAL_HEURISTIC]: Guardrail Heuristics:\n" + "\n".join([str(r) for r in rules[:3]])))
        except:
            pass

    # First Invoke to check for immediate tool calls
    from src.graph.nodes.common_vli import _run_node_with_tiered_fallback
    from src.prompts.planner_model import Plan as PlanSchema

    logger.info("[VLI_SPINE] Initiating Phase A Tiered Fallback Invocation...")
    fallback_msgs_all = []
    response = None
    try:
        # Phase A: Initial Parsing (Strict Direct Response check)
        # We use is_structured=True to easily check has_enough_context
        plan_obj_a, fb_msgs1 = await _run_node_with_tiered_fallback(
            "parser", 
            state_for_prompt, 
            config, 
            tools=tools, 
            messages=messages,
            is_structured=True,
            structured_schema=PlanSchema
        )
        fallback_msgs_all.extend(fb_msgs1)
        
        if plan_obj_a is None:
            plan_obj_a = PlanSchema(
                locale="en-US", 
                has_enough_context=False, 
                thought="Parser returned None. Falling back to default plan.", 
                title="Parser Fallback",
                steps=[],
                direct_response=""
            )
            
        dr = getattr(plan_obj_a, "direct_response", "") or ""
        response = AIMessage(content=str(dr), name="parser_logic")
        
        # If we got a terminal error, we must explain it but keep the UI clean
        # [HARDENING] Check for 'Agent Intelligence Failure' or prompt leakage
        res_content = str(getattr(response, "content", "")).upper()
        is_leak = any(x in res_content for x in ["# SECURITY OVERRIDE", "APEX 500 SYSTEM", "OPERATIONAL MANDATE"])
        
        if getattr(response, "name", None) == "system_fallback_error" or "FAILURE" in res_content or is_leak:
             # Omit final_report to keep report window CLEAR (it will show 'Awaiting Results')
             return Command(
                 update={"messages": fallback_msgs_all + [response]},
                 goto=END
             )
    except Exception as e:
        logger.error(f"[VLI_SPINE] Phase A tiered fallback CRASHED: {e}")
        raise e

    # Fast-Path Check
    tech_keywords = ["compare", "vs", "versus", "analyze", "analysis", "calendar", "smc", "sortino", "sharpe", "report", "markets", "outlook", "geopolitical", "likely", "happen", "explain", "recommend", "suggest", "does"]
    is_technical = any(kw in user_query.lower() for kw in tech_keywords)
    
    # Layer 1: Parser Early-Exit (Math / Admin / --DIRECT Override)
    # Whitelist of administrative tools that skip Phase B synthesis (One-sentence direct status)
    ADMIN_DIRECT_TOOLS = ["vli_cache_tick", "clear_vli_diagnostic", "invalidate_market_cache"]
    
    if is_algebra or force_direct_exit or (getattr(plan_obj_a, 'intent', '') == 'EXECUTE_DIRECT'):
        # check if it's a tool-based admin command
        is_admin_tool = False
        if response.tool_calls:
            is_admin_tool = all(tc["name"] in ADMIN_DIRECT_TOOLS for tc in response.tool_calls)

        # [MATH HARDENING V2] Force bypass for ALL algebra
        should_bypass = plan_obj_a.has_enough_context or force_direct_exit or is_admin_tool or is_algebra
        if is_algebra:
            should_bypass = True # Hard-Force
            logger.info("[VLI_SPINE] Hard-forcing algebra bypass to EXECUTE_DIRECT.")

        if should_bypass:
            logger.info(f"[VLI_SPINE] Layer 1 Direct Exit triggered. Force: {force_direct_exit}, Admin: {is_admin_tool}, AlgebraForce: {is_algebra}")
            # Determine intent based on refactored names
            final_intent = plan_obj_a.intent or "MARKET_INSIGHT"
            if "direct" in str(final_intent).lower() or is_algebra or force_direct_exit or is_admin_tool:
                final_intent = "EXECUTE_DIRECT"
            
            # If it's a tool-based admin command, we MUST execute it before returning
            final_msgs = fb_msgs1
            if response.tool_calls and (force_direct_exit or is_admin_tool):
                name_to_tool = {t.name: t for t in tools}
                for tc in response.tool_calls:
                    t = name_to_tool.get(tc["name"])
                    if t:
                        res = await t.ainvoke(tc["args"], config)
                        final_msgs.append(ToolMessage(content=str(res), tool_call_id=tc["id"], name=tc["name"]))
                
                # If we executed tools, we might need a brief status as the final AI message
                direct_res = str(getattr(plan_obj_a, 'direct_response', '') or "Command executed successfully (Direct Sync).")
            else:
                direct_res = str(getattr(plan_obj_a, 'direct_response', '') or "")

            return Command(
                update={
                    "messages": final_msgs + [AIMessage(content=str(direct_res), name="parser_finalize")], 
                    "intent": final_intent,
                    "directive": "Provide ONLY the final direct calculation or status result. NO NARRATIVE.",
                    "metadata": state.get("metadata", {})
                },
                goto=END if (final_intent == "EXECUTE_DIRECT" or is_direct) else "reporter"
            )

    if response.tool_calls and not is_technical:
        logger.info("[VLI_SPINE] Fast-Path Bypass triggered.")
        name_to_tool = {t.name: t for t in tools}
        sem = asyncio.Semaphore(3)

        async def run_t(tc):
            async with sem:
                t = name_to_tool.get(tc["name"])
                if t:
                    res = await t.ainvoke(tc["args"], config)
                    return ToolMessage(content=str(res), tool_call_id=tc["id"], name=tc["name"])
                return ToolMessage(content="Tool not found", tool_call_id=tc["id"], name=tc["name"])

        t_msgs = list(await asyncio.gather(*[run_t(tc) for tc in response.tool_calls]))
        synth_messages = (
            messages
            + [response]
            + t_msgs
            + [HumanMessage(content="Synthesize these results. If this is a system or cache command, respond ONLY with a 1-sentence execution status (e.g. 'Status: OK'). Otherwise, provide a concise, high-fidelity conversational summary of the fetched data.")]
        )
        
        try:
             final_synth, fb_msgs2 = await _run_node_with_tiered_fallback("coordinator", state_for_prompt, config, messages=synth_messages)
        except Exception as e:
             logger.error(f"Reporter Synthesis Error after fallback: {str(e)}")
             final_report_text = "Analysis completed. (PHASE_SYNTHESIS_INTERRUPTED): The reasoning engine experienced a structural validation failure. Standardized output logic is active."
             return Command(update={"final_report": final_report_text}, goto=END)

        # [NEW] Prepend fallback warnings to chat answer
        fallback_prefix = "\n".join([f"**{str(m.content)}**" for m in fb_msgs1 + fb_msgs2 if m.name == "system_fallback"])
        
        if isinstance(final_synth.content, list):
            extracted_text = "".join([str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in final_synth.content])
        else:
            extracted_text = str(final_synth.content)
            
        final_answer = f"{fallback_prefix}\n\n{extracted_text}" if fallback_prefix else extracted_text

        # Check for admin/direct intent (Hardened to use centralized Layer 0 flag)
        # Fast-Path tool execution should always bypass the heavy reporter module
        should_bypass_reporter = True
        
        return Command(
            update={
                "messages": fb_msgs1 + [response] + t_msgs + fb_msgs2 + [AIMessage(content=final_answer, name="vli_coordinator")],
                "intent": "EXECUTE_DIRECT",
                "metadata": state.get("metadata", {})
            }, 
            goto=END
        )

    # 5. Phase B: Planning & Coordination
    # If not fast-path, we need a Plan
    from src.prompts.planner_model import Plan as PlanSchema
    messages_coord = apply_prompt_template("coordinator", state_for_prompt)

    # [NEW] Immediate Telemetry Injection for Visibility during long planning stalls
    try:
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        with open(telemetry_file, "a", encoding="utf-8") as tf:
            tf.write(f"\n{timestamp} **PHASE_B_EXECUTION:** Coordinator triggered. Model: `{llm_type.upper()}`. Context: {len(str(messages_coord))} chars.\n")
            tf.flush()
    except:
        pass

    try:
        plan_obj, fb_msgs3 = await _run_node_with_tiered_fallback("coordinator", state_for_prompt, config, tools=tools, is_structured=True, structured_schema=PlanSchema, messages=messages_coord)
        fallback_msgs_all.extend(fb_msgs3)
        
        if plan_obj is None:
            raise ValueError("Coordinator returned None")
        
        # [BUGFIX: QUOTA PROPAGATION] Safe exit on quota failure instead of downstream exception
        is_quota_failure = False
        quota_thought = ""
        if isinstance(plan_obj, dict):
            is_quota_failure = plan_obj.get("title") == "Quota Failure"
            quota_thought = plan_obj.get("thought", "RESOURCE_EXHAUSTED: System quota reached.")
        else:
            is_quota_failure = getattr(plan_obj, "title", None) == "Quota Failure"
            quota_thought = getattr(plan_obj, "thought", "RESOURCE_EXHAUSTED: System quota reached.")
            
        if is_quota_failure:
            # We are in VLI Tier 3 Drop-out
            cmd = Command(
                update={"messages": fallback_msgs_all + [
                    # We inject a simulated AIMessage so the UI parses the fallback sequence
                    AIMessage(content="[VLI_SPINE] Quota limit reached on Tier 3 fallback. Managed Processing Recovery initiated.", name="coordinator")
                ]},
                goto="reporter"
            )
            print("====== QUOTA COMMAND ======")
            print("Update keys:", cmd.update.keys())
            print("Goto:", cmd.goto)
            print("===========================")
            return cmd
            
    except Exception as e:
        logger.error(f"[VLI_SPINE] Structural Parsing Failure: {e}. Falling back to high-fidelity research plan.")
        # [RECOVERY] If JSON schema fails, force a safe default but HIGH-DEPTH research plan
        plan_obj = PlanSchema(
            locale="en-US", 
            has_enough_context=False, 
            thought=f"Structural Failure Recovery: Execution continuity maintained despite parsing error: {e}", 
            title="Managed Processing Recovery: Institutional Depth Maintained",
            steps=[Step(
                need_search=True, 
                title="Institutional Research Recovery", 
                description=f"Generate a COMPREHENSIVE institutional report for: {user_query}. You MUST provide a full, multiple paragraph analysis.", 
                step_type=StepType.SYNTHESIZER
            )],
        )

    # 2. Conceptual/Strategy Detection
    QUESTION_WORDS = ["what", "how", "why", "describe", "define", "meaning", "mean", "explain", "info"]
    ADVISORY_WORDS = ["recommend", "should i", "can i", "what if", "how about", "consider", "suggest", "watchlist"]
    STRATEGY_KEYWORDS = ["outlook", "strategy", "approach", "behavior", "macro", "scenario", "this week", "next week"]
    
    is_question = original_human_query.endswith("?") or any(original_human_query.lower().startswith(w) for w in QUESTION_WORDS)
    is_advisory = any(kw in original_human_query.lower() for kw in ADVISORY_WORDS)
    is_strategy = any(kw in original_human_query.lower() for kw in STRATEGY_KEYWORDS)
    is_sentiment = ("sentiment" in original_human_query.lower() or "news" in original_human_query.lower()) and not force_direct_exit

    # 3. Tactical/Command Detection (Imperatives)
    tactical_keywords = ["analyze", "analysis", "smc", "sortino", "sharpe", "report", "get", "run", "scan", "check", "calculate", "audit"]
    is_tactical = any(original_human_query.lower().startswith(kw) for kw in ["get", "run", "analyze", "scan", "check", "calculate", "audit"]) or any(kw in original_human_query.lower() for kw in ["smc", "sortino", "sharpe"])

    # 4. Admin/Fast-Path Detection (Diagnostics/Sync)
    # [v3 Hardening] is_admin is now detected at Layer 0 to fix scoping

    # Route Priority: Admin (Direct) -> Advisory (Tactical) -> Question/Strategy (Synthesis) -> Tactical (Audit)
    # [HARDENING] is_admin always forces specialist override to ensure correct tool access
    is_hard_tactical = any(original_human_query.lower().startswith(kw) for kw in ["get", "run", "analyze", "scan", "check", "calculate", "audit"])
    
    # We trigger the override if it's admin, or if the model failed to plan steps, or if it's an explicit advisory/question that lacks hard keywords
    if (is_admin or is_sentiment or ((is_question or is_advisory or is_strategy) and not is_hard_tactical) or not plan_obj.steps):
        
        logger.warning(f"[VLI_SPINE] Guardrail: Intent detected (Q: {is_question}, Adv: {is_advisory}, S: {is_strategy}, T: {is_tactical}, A: {is_admin}). Forcing specialist node.")
        plan_obj.has_enough_context = False
        plan_obj.direct_response = ""
        
        # Priority Logic: Advisory always forces rigorous tactical authorization 
        if is_advisory:
            target_step_type = StepType.SMC_ANALYST
            step_title = "Institutional Execution Authorization"
            plan_obj.intent = "TACTICAL_EXECUTION"
        elif is_sentiment:
            plan_obj.intent = "SENTIMENT_REPORT"
            plan_obj.title = "Institutional Sentiment Deep-Dive"
            plan_obj.steps = [
                Step(
                    need_search=False,
                    title="Price Behavior Scan",
                    description="Fetch 30-day price history and provide a high-fidelity narrative summary of price drivers for " + user_query,
                    step_type=StepType.ANALYST
                ),
                Step(
                    need_search=True,
                    title="Social Pulse and News Sentiment",
                    description="Search specifically for sentiment on Twitter/X and RSS feeds, then dynamically expand to Reddit for " + user_query,
                    step_type=StepType.SYNTHESIZER
                ),
                Step(
                    need_search=True,
                    title="Catalysts and Sector Context",
                    description="Identify upcoming corporate catalysts and sector-wide news impact for " + user_query,
                    step_type=StepType.SYNTHESIZER
                )
            ]
            return Command(
                update={
                    "current_plan": plan_obj,
                    "intent": "SENTIMENT_REPORT",
                    "steps_completed": 0,
                    "research_topic": plan_obj.title,
                    "messages": fallback_msgs_all + [AIMessage(content=f"[VLI_SPINE] Orchestrating Sentiment Deep-Dive for {user_query}...", name="coordinator")],
                    "metadata": state.get("metadata", {})
                },
                goto=plan_obj.steps[0].step_type.value
            )
        elif (is_question or is_strategy) and not is_hard_tactical:
            target_step_type = StepType.SYNTHESIZER
            step_title = "Institutional Market Insight"
        elif is_admin:
            target_step_type = StepType.SYSTEM
            step_title = "System Administrative Sync"
        elif "smc" in user_query.lower() or "smart money" in user_query.lower():
            target_step_type = StepType.SMC_ANALYST
            step_title = "Institutional SMC Audit"
            plan_obj.intent = "TACTICAL_EXECUTION"
        else:
            target_step_type = StepType.ANALYST
            step_title = "Institutional Technical Audit"

        plan_obj.steps = [Step(
            need_search=(is_question or is_strategy), 
            title=step_title, 
            description=f"FAST_PATH_ADMIN: {user_query}" if is_admin else f"Generate a COMPREHENSIVE institutional analysis for: {user_query}", 
            step_type=target_step_type
        )]
        
        # Inject admin intent to the plan for the reporter to see
        if is_admin:
            plan_obj.intent = "EXECUTE_DIRECT"

    # Robust Intent Check
    plan_intent = getattr(plan_obj, "intent", "") if isinstance(plan_obj, Plan) else plan_obj.get("intent", "")
    state_intent = state.get("intent", "")

    # Handle direct response from plan
    if plan_obj.has_enough_context or plan_obj.direct_response:
        resp = plan_obj.direct_response or f"Understood: {plan_obj.title}"
        
        # [NEW] Prepend fallback warnings
        fallback_prefix = "\n".join([f"**{str(m.content)}**" for m in fallback_msgs_all if getattr(m, 'name', '') == "system_fallback"])
        final_answer = f"{fallback_prefix}\n\n{resp}" if fallback_prefix else resp
        
        is_direct = (plan_intent == "EXECUTE_DIRECT") or (state_intent == "EXECUTE_DIRECT")
        
        return Command(
            update={
                "current_plan": plan_obj, 
                "intent": "EXECUTE_DIRECT" if is_direct else state_intent, # Propagate to top-level
                "messages": fallback_msgs_all + [AIMessage(content=final_answer, name="vli_coordinator")],
                "metadata": state.get("metadata", {})
            }, 
            goto=END if is_direct or state.get("raw_data_mode") else "reporter"
        )

    # 6. Dispatch to Router Logic
    logger.info(f"[VLI_SPINE] Dispatching Plan: {plan_obj.title} ({len(plan_obj.steps)} steps)")

    next_agent = plan_obj.steps[0].step_type.value


    cmd = Command(
        update={
            "current_plan": plan_obj, 
            "intent": "EXECUTE_DIRECT" if is_admin else (plan_intent or state_intent or "MARKET_INSIGHT"),
            "steps_completed": 0, 
            "research_topic": plan_obj.title, 
            "locale": plan_obj.locale,
            "messages": fallback_msgs_all + [AIMessage(content=f"[VLI_SPINE] Plan generated: {plan_obj.title}", name="coordinator")],
            "metadata": state.get("metadata", {})
        }, 
        goto=next_agent
    )
    # print("====== RETURNING COMMAND ======")
    # print("Update:", cmd.update)
    # print("Goto:", cmd.goto)
    # print("===============================")
    return cmd
