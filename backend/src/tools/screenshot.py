# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Agent: Scout - Automated screenshot and visual capture tools.
# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates

# SPDX-License-Identifier: MIT

import asyncio
import base64
import logging
from typing import Annotated, Dict, Any

from langchain_core.tools import tool

from .decorators import log_io
from .shared_storage import SCOUT_CONTEXT

logger = logging.getLogger(__name__)

# Agent-specific resource context (Shared by all Scout sub-modules)
_NODE_RESOURCE_CONTEXT = SCOUT_CONTEXT


def _snapper_worker(url: str) -> str:
    """Synchronous worker for local screen capture using PIL."""
    try:
        from PIL import ImageGrab
        import io
        
        logger.info(f"Taking a snapshot of the local screen in place of {url}...")
        
        # Take screenshot of the primary monitor
        screenshot = ImageGrab.grab()
        
        # Save to bytes buffer
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        screenshot_bytes = buffer.getvalue()
        
        # Encode to base64
        import json
        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        return json.dumps({"images": [f"data:image/png;base64,{b64}"]})
        
    except Exception as e:
        import json
        error_msg = f"Failed to take local screenshot. Error: {repr(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@tool
@log_io
async def snapper(
    url: Annotated[str, "The URL of the webpage or chart to take a snapshot of. If you need to capture the user's actual desktop/screen, pass 'desktop' as the URL."],
) -> str:
    """Use this to capture a full-resolution PNG image snapshot of a website, chart, or the user's local desktop screen. This is the preferred tool when visual layout or graphical data (like TradingView or the active Windows desktop) is required."""
    # Execute the synchronous worker in a separate thread to avoid Windows event loop policy conflicts
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _snapper_worker, url)
