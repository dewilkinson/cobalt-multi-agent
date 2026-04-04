import logging
import os
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type
from src.prompts.template import apply_prompt_template

from ..types import State

logger = logging.getLogger(__name__)


async def reporter_node(state: State):
    # 1. Telemetry Logging: Mark session as synthesizing
    try:
        from src.config.vli import get_vli_path
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open(telemetry_file, "a", encoding="utf-8") as f:
            f.write(f"### [{timestamp}] VLI Transaction Update\n- **Session Status**: `SYNTHESIZING`\n- **Action**: Generating final intelligence report...\n\n---\n")
    except Exception as e:
        logger.error(f"Failed to log synthesis start: {e}")

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

    except Exception as e:
        logger.error(f"Reporter Synthesis Error: {e}")
        final_report_text = "Analysis completed. (Synthesis failed, check logs)"

    return {"final_report": final_report_text}
