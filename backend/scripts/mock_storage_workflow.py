from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio
import json
import random
import logging

import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(dotenv_path=env_path)

# Inject dummy API keys completely bypassing Pydantic environment validation
os.environ["OPENAI_API_KEY"] = "mock-key-for-ui-test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["ANTHROPIC_API_KEY"] = "mock-key"
os.environ["GEMINI_API_KEY"] = "mock-key"
if not os.environ.get("OBSIDIAN_VAULT_PATH"):
    os.environ["OBSIDIAN_VAULT_PATH"] = "c:\\github\\obsidian-vault"

# Append packages/harness to Python Path so deerflow resolves
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "packages", "harness")))

from deerflow.agents.memory.storage import FileMemoryStorage, ObsidianMemoryStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CMA Network Visualizer Mock Server")

# Allow Next.js requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def event_generator():
    """Generates server-sent events for the network visualization."""
    
    # Send structure defining the grid
    init_payload = {
        "type": "init",
        "nodes": [
            {"id": "agent-planner", "type": "agent", "label": "Lead Planner"},
            {"id": "agent-researcher", "type": "agent", "label": "Researcher"},
            {"id": "agent-writer", "type": "agent", "label": "Writer"},
            {"id": "storage-global", "type": "storage", "label": "Global Cache"},
            {"id": "storage-local", "type": "storage", "label": "Local Memory (JSON)"},
            {"id": "storage-obsidian", "type": "storage", "label": "Obsidian Vault (.md)"}
        ]
    }
    yield f"data: {json.dumps(init_payload)}\n\n"
    
    file_storage = FileMemoryStorage()
    obsidian_storage = ObsidianMemoryStorage()
    from deerflow.community.obsidian.tools import _resolve_obsidian_path

    def transmit(action: str, source: str, target: str, message: str, result: str = "none"):
        payload = {
            "type": "event",
            "action": action, 
            "source": source,
            "target": target,
            "message": message,
            "result": result
        }
        return f"data: {json.dumps(payload)}\n\n"

    try:
        # Phase 0: Cleanup previous thrash data
        vault_path = os.environ.get("OBSIDIAN_VAULT_PATH", "c:\\github\\obsidian-vault")
        thrash_root = Path(vault_path) / "_cobalt" / "_memory" / "thrash"
        if thrash_root.exists():
            import shutil
            shutil.rmtree(thrash_root)
            logger.info("Purged previous thrash data at %s", thrash_root)
            yield transmit("clean", "storage-obsidian", "storage-obsidian", "Purged previous thrash data")

        # Phase 1: Boot Sequence
        await asyncio.sleep(1)
        yield transmit("spin-up", "agent-planner", "agent-planner", "Network Controller Online")
        await asyncio.sleep(0.5)
        yield transmit("spin-up", "agent-researcher", "agent-researcher", "Data Crawler Ready")
        await asyncio.sleep(0.5)
        yield transmit("spin-up", "agent-writer", "agent-writer", "Prose Generator Active")

        # Phase 2: High-Volume Storage Thrash
        folders = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
        agents = ["agent-planner", "agent-researcher", "agent-writer"]
        
        add_log_event = lambda m: f"data: {json.dumps({'type': 'event', 'action': 'info', 'message': m})}\n\n"
        yield add_log_event("Starting Multi-Folder Storage Thrash...")

        # Phase 2: Systematic Storage Thrash (Fills & Hits)
        folders = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
        agents = ["agent-planner", "agent-researcher", "agent-writer"]
        
        add_log_event = lambda m: f"data: {json.dumps({'type': 'event', 'action': 'info', 'message': m})}\n\n"
        yield add_log_event("Starting Multi-Phase Cache Stress Test...")

        # A: Intentional Misses (Read from empty slots)
        yield add_log_event("[PHASE A] Measuring Cold Start Latency (Misses)...")
        for i in range(1, 11):
            folder = folders[i % 5]
            agent_id = agents[i % 3]
            yield transmit("read", "storage-obsidian", agent_id, f"Cache miss in {folder} (Slot {i})", "miss")
            await asyncio.sleep(0.1)

        # B: Dense Writes (Filling the Vault)
        yield add_log_event("[PHASE B] Populating Storage Matrix (Writes)...")
        for i in range(1, 31):
            folder = folders[i % 5]
            agent_id = agents[i % 3]
            agent_name = agent_id.split("-")[1]
            target_path = f"thrash/{folder}/{agent_name}_update_{i}"
            full_path = _resolve_obsidian_path(f"_cobalt/_memory/{target_path}.md")
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {"iteration": i, "timestamp": datetime.utcnow().isoformat(), "payload": "Resident Data"}
            content = f"---\nresidency: true\n---\n# Data Block {i}\n\n```json\n{json.dumps(data, indent=2)}\n```"
            full_path.write_text(content, encoding="utf-8")
            
            yield transmit("write", agent_id, "storage-obsidian", f"Wrote to {folder}/segment_{i}", "success")
            await asyncio.sleep(0.1)

        # C: Read Hits (Verifying Performance)
        yield add_log_event("[PHASE C] Verifying Sub-Millisecond Access (Hits)...")
        for i in range(1, 21):
            folder = folders[(i+5) % 5]
            agent_id = agents[i % 3]
            yield transmit("read", "storage-obsidian", agent_id, f"Read hit from {folder}/segment_{i}", "hit")
            await asyncio.sleep(0.1)

        # D: Final Random Thrash (Stress)
        yield add_log_event("[PHASE D] High-Concurrency Mock Load...")
        for i in range(31, 61):
            folder = random.choice(folders)
            agent_id = random.choice(agents)
            action = random.choice(["read", "write"])
            
            if action == "write":
                yield transmit("write", agent_id, "storage-obsidian", f"Wrote to {folder}/final_{i}", "success")
            else:
                yield transmit("read", "storage-obsidian", agent_id, f"Read from {folder}/cache_{i}", "hit")
            await asyncio.sleep(random.uniform(0.05, 0.15))
        yield transmit("write", "agent-planner", "storage-global", "Committed thrash manifest to Global Cache")

        # Final Verification Phase
        yield add_log_event("Verifying resident files in Vault...")
        await asyncio.sleep(1)
        yield transmit("complete", "storage-obsidian", "agent-planner", "Persistence Verified (Resident/Thrash)")

        # End of stream flag
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"

    except Exception as e:
        logger.error(f"Error in simulation: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.get("/api/simulate")
async def simulate_network():
    """Starts the network workflow visualization test."""
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    # Make sure we run on 8001 to not conflict with normal backend
    uvicorn.run("mock_storage_workflow:app", host="0.0.0.0", port=8001, reload=True)
