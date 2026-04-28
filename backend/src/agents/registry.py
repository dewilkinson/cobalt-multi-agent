# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AgentRegistry:
    """A registry for managing agent configurations in a modular way."""

    def __init__(self, definitions_dir: str):
        self.definitions_dir = definitions_dir
        self.agents: dict[str, dict[str, Any]] = {}
        self.load_definitions()

    def load_definitions(self):
        """Loads all agent definitions from the JSON files in the definitions directory."""
        if not os.path.exists(self.definitions_dir):
            logger.warning(f"Agent definitions directory not found: {self.definitions_dir}")
            return

        logger.info(f"Loading agent definitions from {self.definitions_dir}")
        for filename in os.listdir(self.definitions_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.definitions_dir, filename)
                try:
                    with open(path, encoding="utf-8") as f:
                        config = json.load(f)
                        agent_type = config.get("type")
                        if agent_type:
                            self.agents[agent_type] = config
                            logger.info(f"Loaded agent definition: {agent_type}")
                except Exception as e:
                    logger.error(f"Error loading agent definition from {path}: {str(e)}")

    def get_agent_config(self, agent_type: str) -> dict[str, Any] | None:
        """Retrieves the configuration for a specific agent type."""
        return self.agents.get(agent_type)

    def list_agents(self) -> list[str]:
        """Returns a list of all registered agent types."""
        return list(self.agents.keys())


# Initialize the registry with the default path
_current_dir = Path(__file__).parent.resolve()
_defs_path = _current_dir / "definitions"
registry = AgentRegistry(str(_defs_path))
# Trigger reload 4
