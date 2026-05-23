import asyncio
import os
import sys
from uuid import uuid4

# Setup Environment
os.environ["OBSIDIAN_VAULT_PATH"] = "c:/github/obsidian-vault"
sys.path.append("C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend")

from langchain_core.messages import HumanMessage

from src.graph.builder import graph


async def debug_call():
    vli_command = "Portfolio Manager, clear my 'Daily Picks' watchlist."

    config = {"configurable": {"thread_id": str(uuid4()), "obsidian_settings": {"OBSIDIAN_VAULT_PATH": os.environ["OBSIDIAN_VAULT_PATH"]}}}

    initial_state = {"messages": [HumanMessage(content=vli_command)], "research_topic": vli_command}

    print(f"Invoking graph with: {vli_command}")
    result = await graph.ainvoke(initial_state, config)

    print("\n--- Message Log ---")
    for i, msg in enumerate(result.get("messages", [])):
        role = getattr(msg, "name", "AI/User")
        print(f"[{i}] {role}: {msg.content[:100]}...")

    # Check if the file was actually created/cleared
    target_file = "c:/github/obsidian-vault/_cobalt/Watchlist_Daily Picks.md"
    print(f"\nChecking file: {target_file}")
    if os.path.exists(target_file):
        print("File EXISTS.")
        with open(target_file) as f:
            print(f"Content: {f.read()}")
    else:
        print("File DOES NOT exist.")


if __name__ == "__main__":
    asyncio.run(debug_call())
