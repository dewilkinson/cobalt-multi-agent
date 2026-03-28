# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
import base64
import httpx
import os
from pathlib import Path
from langchain_core.tools import tool

from typing import Dict, Any
from .shared_storage import SCOUT_CONTEXT

logger = logging.getLogger(__name__)

from src.tools.shared_storage import SCOUT_CONTEXT, GLOBAL_CONTEXT

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by all Scout sub-modules
_SHARED_RESOURCE_CONTEXT = SCOUT_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


def _get_base64_image(image_path: str):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

@tool
async def get_image_from_url(url: str) -> str:
    """
    Downloads an image from an HTTP URL and prepares it for vision analysis.
    Use this when the user provides a link to a chart or statement.
    """
    try:
        logger.info(f"Downloading image from URL: {url}")
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            ext = url.split('.')[-1].lower() if '.' in url else 'png'
            mime_type = f"image/{ext}" if ext in ['png', 'jpg', 'jpeg', 'webp'] else "image/png"
            b64_data = base64.b64encode(response.content).decode('utf-8')
            return f"[IMAGE_LOADED]: Source={url}, MIME={mime_type}, Data=data:{mime_type};base64,{b64_data}"
    except Exception as e:
        logger.error(f"Error fetching image from URL: {e}")
        if "desktop" in url.lower():
            return f"[ERROR]: Failed to download image from {url}: Request URL is missing an 'http://' or 'https://' protocol. HINT: Use the 'snapper' tool with url='desktop' to capture the local screen instead."
        return f"[ERROR]: Failed to download image from {url}: {str(e)}"

@tool
def get_image_from_local_path(path: str) -> str:
    """
    Reads an image from a local file system path and prepares it for vision analysis.
    Use this when the user references a local file (e.g., 'C:\\Users\\...\\chart.png').
    """
    try:
        logger.info(f"Reading local image: {path}")
        if not os.path.exists(path):
            return f"[ERROR]: File not found at {path}"
        
        ext = path.split('.')[-1].lower()
        mime_type = f"image/{ext}" if ext in ['png', 'jpg', 'jpeg', 'webp'] else "image/png"
        b64_data = _get_base64_image(path)
        return f"[IMAGE_LOADED]: Source={path}, MIME={mime_type}, Data=data:{mime_type};base64,{b64_data}"
    except Exception as e:
        logger.error(f"Error reading local image: {e}")
        return f"[ERROR]: Failed to read image from {path}: {str(e)}"
