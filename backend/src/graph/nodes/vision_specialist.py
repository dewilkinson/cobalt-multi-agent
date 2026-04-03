# Agent: Vision Specialist - Node definition for technical chart scans.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import os
import logging
from typing import Dict, Any
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from src.tools.shared_storage import GLOBAL_CONTEXT
from src.config.vli import get_vli_path, SPECIALIZATION_FILE
from ..types import State
from .common_vli import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

async def vision_specialist_node(state: State, config: RunnableConfig):
    """Vision Specialist node implementation."""
    logger.info("Vision Specialist Node: Initializing high-fidelity technical scan.")
    
    # 1. READ SPECIALIZATION CONTEXT
    specialization_content = ""
    special_file = get_vli_path(SPECIALIZATION_FILE)
    if os.path.exists(special_file):
        with open(special_file, "r", encoding="utf-8") as f:
            specialization_content = f.read()
            
    # 2. READ CHART SPECIFICATIONS (Optional Layout Context)
    layout_content = ""
    layout_file = get_vli_path("chart_specifications.md")
    if os.path.exists(layout_file):
        with open(layout_file, "r", encoding="utf-8") as f:
            layout_content = f.read()

    # 3. PREPARE INSTRUCTIONS
    instructions = (
        f"You MUST use the following technical specialization and layout context to parse all provided images.\n\n"
        f"--- CHART LAYOUT & SPECIFICATIONS ---\n"
        f"{layout_content}\n"
        f"--------------------------------------\n\n"
        f"--- TECHNICAL INDICATOR SCHEMA ---\n"
        f"{specialization_content}\n"
        f"----------------------------------\n"
    )

    # 3. EXECUTE VISION SCAN
    # Gemini 1.5 Pro will handle the multimodal input automatically from the state messages
    # The _setup_and_execute_agent_step helper will find the images in the most recent HumanMessage
    result = await _setup_and_execute_agent_step(
        state, 
        config, 
        "vision_specialist", 
        [], 
        agent_instructions=instructions
    )

    # 4. CONTEXT HYGIENE: PURGE RAW IMAGES
    # After the Vision Specialist extracts the text, we strip the heavy base64 blobs
    # from the message history to keep the 'Trading LLM Space' clean.
    new_messages = []
    for msg in state.get("messages", []):
        if isinstance(msg, HumanMessage) and isinstance(msg.content, list):
            # Strip the image parts from the human message, keeping only the text
            clean_text = ""
            for part in msg.content:
                if isinstance(part, str):
                    clean_text += part
                elif isinstance(part, dict) and part.get("type") == "text":
                    clean_text += part.get("text", "")
            
            # Replace multimodal content with its clean text equivalent
            msg.content = clean_text
            new_messages.append(msg)
        else:
            new_messages.append(msg)
    
    # Add the Vision Specialist's summary message
    if "messages" in result:
        new_messages.extend(result["messages"])
        result["messages"] = new_messages
    else:
        result["messages"] = new_messages

    return result
