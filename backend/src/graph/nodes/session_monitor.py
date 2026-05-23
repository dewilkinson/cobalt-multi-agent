# Agent: Session Monitor - Node definition for workflow tracking.
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

import logging
import os

from langchain_core.runnables import RunnableConfig

from ..types import State
from .common_vli import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)


async def session_monitor_node(state: State, config: RunnableConfig):
    """Session Monitor node implementation."""
    logger.info("Session Monitor Node: Analyzing raw telemetry backlog.")

    # Read the telemetry backlog
    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    backlog_content = "No telemetry backlog found."
    telemetry_file = None

    if vault_path:
        cobalt_dir = os.path.join(vault_path, "_cobalt")
        telemetry_file = os.path.join(cobalt_dir, "VLI_Raw_Telemetry.md")
        if os.path.exists(telemetry_file):
            with open(telemetry_file, encoding="utf-8") as f:
                backlog_content = f.read()

    # Inject the backlog explicitly into the prompt context via instructions
    # Note: the actual agent system prompt is loaded via the registry + .md framework
    # The `agent_instructions` variable adds a dynamic final human message wrapper in common_vli
    instructions = (
        f"The following is the raw backlog of VLI telemetry operations.\n"
        f"Please analyze it according to your core directives and return a detailed Daily Report tailored to the user.\n\n"
        f"--- RAW TELEMETRY BACKLOG ---\n"
        f"{backlog_content}\n"
        f"-----------------------------\n"
    )

    # Execute the agent
    tools = []  # Pure analysis based on the ingested state
    result = await _setup_and_execute_agent_step(state, config, "session_monitor", tools, agent_instructions=instructions)

    # If successful, archive/clear the telemetry queue
    if telemetry_file and os.path.exists(telemetry_file):
        try:
            with open(telemetry_file, "w", encoding="utf-8") as f:
                f.write("<!-- Daily Backlog Cleared by Session Monitor -->\n")
        except Exception as e:
            logger.error(f"Failed to clear telemetry backlog: {e}")

    return result
