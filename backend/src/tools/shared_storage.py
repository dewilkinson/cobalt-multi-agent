# Agent: Scout - Shared agent resource contexts for persistence.
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

from typing import Dict, Any

# Centralized Agent Contexts (Durable during node execution)
# Each agent node has only one context shared by all sub-modules
# These are initialized when the agent spins up and should be cleared on termination if needed.

SCOUT_CONTEXT: Dict[str, Any] = {}
ANALYST_CONTEXT: Dict[str, Any] = {}
JOURNALER_CONTEXT: Dict[str, Any] = {}
CODER_CONTEXT: Dict[str, Any] = {}
SENTINEL_RM_CONTEXT: Dict[str, Any] = {}
ORCHESTRATOR_CONTEXT: Dict[str, Any] = {}
PROSE_CONTEXT: Dict[str, Any] = {}
PPT_CONTEXT: Dict[str, Any] = {}

# Global Shared Context (Visible to all agents of any type)
GLOBAL_CONTEXT: Dict[str, Any] = {}
GENERAL_CONTEXT = GLOBAL_CONTEXT # Alias for compatibility
