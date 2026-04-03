import os
import json
import logging
from datetime import datetime
from typing import Dict, Any
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from src.prompts.template import apply_prompt_template
from src.llms.llm import get_llm_by_type
from src.config.agents import AGENT_LLM_MAP
from ..types import State

logger = logging.getLogger(__name__)

async def reporter_node(state: State):
    """Reporter node implementation with AI synthesis."""
    logger.info("Reporter Node: Synthesizing final session briefing.")
    # Telemetry logging has been moved to the bottom of the function to ensure the dashboard waits until synthesis is complete.
            
    # 2. Dynamic Synthesis
    if state.get("final_report"):
        return {}

    try:
        # Load synthesis LLMs
        llm = get_llm_by_type(AGENT_LLM_MAP.get("reporter", "basic"))
        
        # [RESILIENCE] History Compaction:
        # If we have a massive history (e.g. from macro fetch), prune tool noise.
        raw_messages = state.get("messages", [])
        start_time = datetime.now()
        
        if len(raw_messages) > 10:
            logger.info(f"Reporter: Compacting history ({len(raw_messages)} messages) for synthesis.")
            compacted = []
            
            # Identify the last tool result (the research finding)
            last_tool_msg = None
            for m in reversed(raw_messages):
                if isinstance(m, ToolMessage):
                    last_tool_msg = m
                    break
            
            for m in raw_messages:
                if isinstance(m, HumanMessage):
                    compacted.append(m)
                elif isinstance(m, AIMessage):
                    name = getattr(m, "name", "")
                    # Keep coordinator plans and the very last results
                    if name in ["coordinator", "vli_coordinator"] or m == raw_messages[-2] or m == raw_messages[-1]:
                        # Ensure large message content is summarized, not just deleted
                        if m.content and len(str(m.content)) > 10000:
                            m.content = str(m.content)[:10000] + "\n... [Content Truncated for Efficiency]"
                        compacted.append(m)
                elif isinstance(m, ToolMessage):
                    # ALWAYS keep the last tool message as it contains the results we are reporting on
                    if m == last_tool_msg:
                        if m.content and len(str(m.content)) > 10000:
                            m.content = str(m.content)[:10000] + "\n... [Large Dataset Pruned]"
                        compacted.append(m)
            
            state_to_synthesize = {**state, "messages": compacted}
        else:
            state_to_synthesize = state

        # Invoke LLM for synthesis
        messages = apply_prompt_template("reporter", state_to_synthesize)
        response = await llm.ainvoke(messages)
        
        # Log performance metrics
        end_time = datetime.now()
        latency = (end_time - start_time).total_seconds()
        from src.utils.vli_metrics import log_vli_metric
        log_vli_metric("reporter", latency, True)
        
        final_report_text = response.content
    except Exception as e:
        logger.error(f"Reporter Synthesis Error: {e}")
        final_report_text = "Analysis completed. (Synthesis failed, check logs)"
        
    # Telemetry Logging: Mark session as complete ONLY AFTER synthesis is done
    try:
        from src.config.vli import get_vli_path
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        os.makedirs(os.path.dirname(telemetry_file), exist_ok=True)
        
        # Extract atomic metrics
        messages_history = state.get("messages", [])
        initial_command = "Unknown"
        agent_sequence = []
        
        current_plan = state.get("current_plan")
        steps = []
        if current_plan:
            steps = getattr(current_plan, "steps", [])
        
        step_idx = 0
        last_name = None
        
        for msg in reversed(messages_history):
            if isinstance(msg, HumanMessage):
                initial_command = str(msg.content)
                break
                
        for msg in messages_history:
            if isinstance(msg, AIMessage) and getattr(msg, "name", None):
                msg_name = msg.name
                
                # Exclude administrative nodes
                if msg_name in ["reporter", "coordinator", "vli_coordinator", "router"]:
                    continue
                    
                # Strict Institutional Name Filter
                valid_nodes = ["scout", "researcher", "analyst", "smc_analyst", "system", "terminal_specialist", "vision_specialist", "journaler"]
                if msg_name not in valid_nodes:
                    continue
                
                # Deduplication
                if msg_name != last_name:
                    display_name = f"**<span style='color: #f0883e;'>{msg_name}</span>**"
                    if step_idx < len(steps):
                        step_title = steps[step_idx].title if hasattr(steps[step_idx], "title") else steps[step_idx].get("title", "Active Step")
                        display_name += f" ({step_title}) "
                        step_idx += 1
                    elif msg_name == "vli_parser":
                        display_name += " (Fast-Path Execution) "
                    
                    agent_sequence.append(display_name)
                    last_name = msg_name

        timestamp = datetime.now().strftime("%H:%M:%S")
        
        agent_list_md = ""
        if agent_sequence:
            agent_list_md = "\n  - " + "\n  - ".join(agent_sequence)
        else:
            agent_list_md = " None"
            
        final_response_preview = final_report_text[:500].strip().replace("\n", " ")

        log_entry = (
            f"### [{timestamp}] VLI Transaction\n"
            f"- **Session Status**: `COMPLETED`\n"
            f"- **Command**: `{initial_command}`\n"
            f"- **Agents Spun Up**: `{len(agent_sequence)}`{agent_list_md}\n"
            f"- **System Response Preview**: {final_response_preview}...\n\n"
            "---\n"
        )
        
        with open(telemetry_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
            
    except Exception as e:
        logger.error(f"Failed to write telemetry: {e}")

    return {"final_report": final_report_text}

