import os
import sys

# Setup Environment AS SEEN in simulation script
os.environ["OBSIDIAN_VAULT_PATH"] = "c:/github/obsidian-vault"
sys.path.append("C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend")

print("--- sys.path ---")
for p in sys.path:
    print(p)

import src.agents.agents as agents

print(f"\nSource of agents.py: {agents.__file__}")

import src.config.agents as config_agents
from src.config.agents import AGENT_LLM_MAP

print(f"Source of config/agents.py: {config_agents.__file__}")

try:
    print(f"Lookup portfolio_manager: {AGENT_LLM_MAP['portfolio_manager']}")
except KeyError:
    print("KeyError: portfolio_manager NOT FOUND in AGENT_LLM_MAP")

# Verify actual content of agents.py as seen by Python
import inspect

print("\n--- Start of create_agent source ---")
print(inspect.getsource(agents.create_agent))
