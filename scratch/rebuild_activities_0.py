"""DeerFlowClient — Embedded Python client for DeerFlow agent system.

Provides direct programmatic access to DeerFlow's agent capabilities
without requiring LangGraph Server or Gateway API processes.

Usage:
    from deerflow.client import DeerFlowClient

    client = DeerFlowClient()
    response = client.chat("Analyze this paper for me", thread_id="my-thread")
    print(response)

    # Streaming
    for event in client.stream("hello"):
        print(event)
"""

import asyncio
import json
import logging
import mimetypes
import shutil
import tempfile
import uuid
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain.agents.factory import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from deerflow.agents.lead_agent.agent import _build_middlewares
from deerflow.agents.lead_agent.prompt import apply_prompt_template
from deerflow.agents.thread_state import ThreadState
from deerflow.config.agents_config import AGENT_NAME_PATTERN
from deerflow.config.app_config import get_app_config, reload_app_config
from deerflow.config.extensions_config import ExtensionsConfig, SkillStateConfig, get_extensions_config, reload_extensions_config
from deerflow.config.paths import get_paths
from deerflow.models import create_chat_model
from deerflow.skills.installer import install_skill_from_archive
from deerflow.uploads.manager import (
    claim_unique_filename,
    delete_file_safe,
    enrich_file_listing,
    ensure_uploads_dir,
    get_uploads_dir,
    list_files_in_dir,
    upload_artifact_url,
    upload_virtual_path,
)

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """A single event from the streaming agent response.

    Event types align with the LangGraph SSE protocol:
        - ``"values"``: Full state snapshot (title, messages, artifacts).
        - ``"messages-tuple"``: Per-message update (AI text, tool calls, tool results).
        - ``"end"``: Stream finished.

    Attributes:
        type: Event type.
        data: Event payload. Contents vary by type.
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)


class DeerFlowClient:
    """Embedded Python client for DeerFlow agent system.

    Provides direct programmatic access to DeerFlow's agent capabilities
    without requiring LangGraph Server or Gateway API processes.

    Note:
        Multi-turn conversations require a ``checkpointer``. Without one,
        each ``stream()`` / ``chat()`` call is stateless — ``thread_id``
        is only used for file isolation (uploads / artifacts).

        The system prompt (including date, memory, and skills context) is
        generated when the internal agent is first created and cached until
        the configuration key changes. Call :meth:`reset_agent` to force
        a refresh in long-running processes.

    Example::

        from deerflow.client import DeerFlowClient

        client = DeerFlowClient()

        # Simple one-shot
        print(client.chat("hello"))

        # Streaming
        for event in client.stream("hello"):
            print(event.type, event.data)

        # Configuration queries
        print(client.list_models())
        print(client.list_skills())
    """

    def __init__(
        self,
        config_path: str | None = None,
        checkpointer=None,
        *,
        model_name: str | None = None,
        thinking_enabled: bool = True,
        subagent_enabled: bool = False,
        plan_mode: bool = False,
        agent_name: str | None = None,
    ):
        """Initialize the client.

        Loads configu