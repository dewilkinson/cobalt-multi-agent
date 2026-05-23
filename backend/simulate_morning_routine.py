import asyncio
import json
import os
import sys
from datetime import datetime
from uuid import uuid4

# Setup Environment
os.environ["OBSIDIAN_VAULT_PATH"] = "c:/github/obsidian-vault"
sys.path.append("C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend")

from langchain_core.messages import AIMessage, HumanMessage

from src.graph.builder import graph

# Simulation Data Store
SIM_HISTORY_PATH = "C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend/simulation_history.json"


async def get_vault_state():
    """Reads the current state of the _cobalt vault for the visualizer."""
    vault_path = os.environ["OBSIDIAN_VAULT_PATH"]
    cobalt_dir = os.path.join(vault_path, "_cobalt")
    state = {}

    # Watchlists
    for list_file in os.listdir(cobalt_dir):
        if list_file.startswith("Watchlist_") and list_file.endswith(".md"):
            name = list_file.replace("Watchlist_", "").replace(".md", "")
            with open(os.path.join(cobalt_dir, list_file)) as f:
                state[f"watchlist_{name}"] = f.read()

    # Journal
    journal_dir = os.path.join(vault_path, "Journals")
    today = datetime.now().strftime("%Y-%m-%d")
    journal_path = os.path.join(journal_dir, f"Trading_Journal_{today}.md")
    if os.path.exists(journal_path):
        with open(journal_path) as f:
            state["journal"] = f.read()
    else:
        state["journal"] = "(Empty)"

    return state


async def run_simulation_step(step_id, vli_command):
    """Executes a single step in the multi-agent graph and records the output."""
    print(f"\n[SIM] Step {step_id}: {vli_command}")

    config = {"configurable": {"thread_id": str(uuid4()), "obsidian_settings": {"OBSIDIAN_VAULT_PATH": os.environ["OBSIDIAN_VAULT_PATH"]}}, "recursion_limit": 100}

    initial_state = {"messages": [HumanMessage(content=vli_command)], "research_topic": vli_command, "is_test_mode": True}

    # Invoke Graph
    result = await graph.ainvoke(initial_state, config)

    # Capture relevant messages (Coordinator thought + Reporter final message)
    thought = ""
    reporter_msg = ""
    for msg in result.get("messages", []):
        if hasattr(msg, "name"):
            if msg.name == "coordinator":
                thought = msg.content
            elif msg.name == "reporter":
                reporter_msg = msg.content
        elif isinstance(msg, AIMessage) and not reporter_msg:
            reporter_msg = msg.content  # Fallback

    vault_state = await get_vault_state()

    step_data = {"step_id": step_id, "command": vli_command, "agent_thought": thought, "reporter_response": reporter_msg, "vault_snapshot": vault_state, "timestamp": datetime.now().isoformat()}

    return step_data


async def main():
    history = []

    commands = [
        "Portfolio Manager, clear my 'Daily Picks' watchlist to start my morning session.",
        "Scout, research AAPL and XOM. I'm looking at Tech vs Energy today.",
        "Add XOM to my 'Daily Picks' as a Shield candidate.",
        "Actually, I've changed my mind. Swap XOM for OXY in my 'Daily Picks' list.",
        "Rerun suitability and risk analysis on my 'Daily Picks' (Summary Mode).",
        "Excellent. Sync my 'Daily Picks' to today's trading journal and finalize the session.",
    ]

    for i, cmd in enumerate(commands, 1):
        step_result = await run_simulation_step(i, cmd)
        history.append(step_result)

        # Write history incrementally for visualizer playback
        with open(SIM_HISTORY_PATH, "w") as f:
            json.dump(history, f, indent=2)

    print("\n[SIM] Simulation Complete. History saved to simulation_history.json")


if __name__ == "__main__":
    asyncio.run(main())
