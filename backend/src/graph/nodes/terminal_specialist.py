# Agent: Terminal Specialist - Node definition for safe shell execution.
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

import json
import logging

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from src.tools import bash_shell_tool, python_repl_tool, snapper

from ..types import State
from .common_vli import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)


async def terminal_specialist_node(state: State, config: RunnableConfig):
    """Terminal Specialist node implementation."""
    logger.info("Terminal Specialist Node: Initializing safe bash execution.")

    tools = [bash_shell_tool, python_repl_tool, snapper]

    # 1. Execute the agent step
    result = await _setup_and_execute_agent_step(state, config, "terminal_specialist", tools)

    # 2. Check for Sensitive Operations (rm/mv)
    last_msg = result.get("messages", [])[-1] if result.get("messages") else None

    # If the tool returned a request for approval (stored in the last message's content as JSON)
    if last_msg and isinstance(last_msg.content, str) and last_msg.content.startswith('{"status": "APPROVAL_REQUIRED"'):
        try:
            approval_data = json.loads(last_msg.content)
            sensitive_cmd = approval_data.get("command")
            reason = approval_data.get("reason")

            logger.warning(f"SENSITIVE COMMAND DETECTED: {sensitive_cmd}. Pausing for human approval.")
        except Exception as e:
            logger.error(f"Error parsing approval data: {e}")
            return result

        # 3. Mandatorily Interrupt for Human-in-the-Loop
        feedback = interrupt(f"APPROVE SENSITIVE COMMAND: {reason}\nCommand: `{sensitive_cmd}`")

        if feedback and str(feedback).upper().startswith("[ACCEPTED]"):
            logger.info(f"User approved sensitive command: {sensitive_cmd}")
            # If approved, we re-invoke the tool with a special bypass flag or just execute it
            # For now, we will simply proceed with a manual subprocess run in the node
            import subprocess

            res = subprocess.run(sensitive_cmd, shell=True, capture_output=True, text=True)
            result["messages"].append(AIMessage(content=f"User approved. Executed `{sensitive_cmd}`.\nOutput: {res.stdout}\nErrors: {res.stderr}", name="terminal_specialist"))
        else:
            logger.info(f"User DENIED sensitive command: {sensitive_cmd}")
            result["messages"].append(AIMessage(content=f"Operation DENIED by user. Command `{sensitive_cmd}` was NOT executed.", name="terminal_specialist"))

    return result
