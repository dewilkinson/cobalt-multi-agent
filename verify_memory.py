# Cobalt Multiagent - High-fidelity financial analysis platform (Tiered Memory Storage)
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""Verification script for Tiered Memory Storage."""

import os
import sys
import json
import logging
from pathlib import Path

# Add backend to path for imports
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "backend", "packages", "harness")))

from deerflow.agents.memory.storage import get_memory_storage
from deerflow.config.memory_config import get_memory_config
from deerflow.config.app_config import get_app_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_memory")

# Initialize config
get_app_config()

def test_registry():
    logger.info("Testing Registry Enforcement...")
    storage = get_memory_storage()
    
    # Authorized ID (already in config.yaml from my edit)
    try:
        storage.load("researcher")
        logger.info("[PASS] Authorized ID 'researcher' allowed.")
    except PermissionError:
        logger.error("[FAIL] Authorized ID 'researcher' denied!")

    # Unauthorized ID
    try:
        storage.load("hacker-agent")
        logger.error("[FAIL] Unauthorized ID 'hacker-agent' allowed!")
    except PermissionError:
        logger.info("[PASS] Unauthorized ID 'hacker-agent' denied (Hard Fail).")

def test_obsidian_storage():
    logger.info("Testing Obsidian Specialist Storage...")
    storage = get_memory_storage()
    # Force use of ObsidianMemoryStorage by checking class (if configured)
    from deerflow.agents.memory.storage import ObsidianMemoryStorage
    if isinstance(storage, ObsidianMemoryStorage):
        logger.info("Using Obsidian Specialist Storage.")
        test_data = {"facts": [], "user": {"workContext": {"summary": "Verified", "updatedAt": "now"}}, "history": {}}
        storage.save(test_data, "researcher")
        
        # Verify markdown wrapping
        obsidian_dir = Path("_cobalt/_memory") 
        if os.getenv("OBSIDIAN_VAULT_PATH"):
             vault = Path(os.getenv("OBSIDIAN_VAULT_PATH"))
             path = vault / "_cobalt" / "_memory" / "agents" / "researcher.md"
             if path.exists():
                 content = path.read_text()
                 if "```json" in content and "Verified" in content:
                     logger.info("[PASS] Obsidian Markdown-wrapped JSON verified.")
                 else:
                     logger.error("[FAIL] Obsidian file content invalid!")
             else:
                 logger.warning("[SKIP] Could not find obsidian file at %s", path)
    else:
        logger.info("Obsidian storage not active, skipping detailed check.")

if __name__ == "__main__":
    test_registry()
    test_obsidian_storage()
    logger.info("Verification Complete.")
