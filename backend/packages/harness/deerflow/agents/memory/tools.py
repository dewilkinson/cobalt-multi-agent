# Cobalt Multiagent - High-fidelity financial analysis platform (Tiered Memory Storage)
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""Tools for manual memory management (Snapshots, Pruning)."""

import logging
from typing import Optional
from langchain.tools import tool
from deerflow.agents.memory.storage import get_memory_storage
from deerflow.agents.memory.updater import prune_memory_from_pool

logger = logging.getLogger(__name__)

@tool("snapshot_memory", parse_docstring=True)
def snapshot_memory(scope: Optional[str] = None) -> str:
    """Create a manual backup (snapshot) of the current memory state.
    
    Args:
        scope: The storage ID to snapshot (e.g., 'global', 'researcher'). 
               Defaults to 'global' if not provided.
    """
    try:
        storage = get_memory_storage()
        # If scope is 'global', pass None to storage
        target = None if scope == "global" or not scope else scope
        backup_path = storage.backup(target)
        return f"Successfully created snapshot: {backup_path}"
    except Exception as e:
        return f"Failed to create snapshot: {str(e)}"

@tool("prune_memory", parse_docstring=True)
def prune_memory(scope: Optional[str] = None) -> str:
    """Manually trigger the weighted pruning algorithm on a specific memory pool.
    
    Facts with low confidence and low importance will be removed until the 
    maximum fact limit is reached.
    
    Args:
        scope: The storage ID to prune (e.g., 'global', 'coder').
               Defaults to 'global' if not provided.
    """
    try:
        target = None if scope == "global" or not scope else scope
        result = prune_memory_from_pool(target)
        return result
    except Exception as e:
        return f"Pruning failed: {str(e)}"
