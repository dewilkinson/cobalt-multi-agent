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
    """Worker for local screen capture or headless browser snapshot using Edge."""
    import os
    import json
    import tempfile
    import subprocess
    import io
    from PIL import ImageGrab
    
    try:
        # Check if we should capture a specific URL via Headless Edge
        if url and url.lower().startswith("http"):
            logger.info(f"VLI_SYSTEM: Capturing headless snapshot of {url}...")
            
            edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            if not os.path.exists(edge_path):
                # Fallback to simple command if path is different (should be rare on this machine)
                edge_path = "msedge"
                
            temp_file = os.path.join(tempfile.gettempdir(), f"vli_snap_{os.getpid()}.png")
            
            # CLI command for headless screenshot
            # --headless=new is the modern Chromium headless mode
            cmd = [
                edge_path,
                "--headless=new",
                f"--screenshot={temp_file}",
                "--window-size=1920,1080",
                "--hide-scrollbars",
                url
            ]
            
            try:
                subprocess.run(cmd, check=True, timeout=15, capture_output=True)
                if os.path.exists(temp_file):
                    with open(temp_file, "rb") as f:
                        screenshot_bytes = f.read()
                    os.remove(temp_file) # Cleanup
                    
                    b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                    return json.dumps({
                        "images": [f"data:image/png;base64,{b64}"],
                        "source": f"Headless Snapshot of {url}"
                    })
                else:
                    raise FileNotFoundError("Edge failed to generate screenshot file.")
            except Exception as e:
                logger.error(f"Headless snap failed: {e}. Falling back to Desktop grab.")
                # Fallback to desktop capture if headless fails
        
        # Default: Capture Desktop
        logger.info(f"Taking a snapshot of the local screen in place of {url}...")
        screenshot = ImageGrab.grab()
        
        # Save to bytes buffer
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        screenshot_bytes = buffer.getvalue()
        
        # Encode to base64
        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        return json.dumps({
            "images": [f"data:image/png;base64,{b64}"],
            "source": "Local Desktop Screen Capture"
        })
        
    except Exception as e:
        error_msg = f"Failed to take snapshot. Error: {repr(e)}"
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
