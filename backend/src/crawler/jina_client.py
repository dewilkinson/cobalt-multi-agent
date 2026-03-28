# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
import os

import requests

logger = logging.getLogger(__name__)


class JinaClient:
    def crawl(self, url: str, return_format: str = "html") -> str:
        headers = {
            "Content-Type": "application/json",
            "X-Return-Format": return_format,
        }
        if os.getenv("JINA_API_KEY"):
            headers["Authorization"] = f"Bearer {os.getenv('JINA_API_KEY')}"
        else:
            logger.warning(
                "Jina API key is not set. Provide your own key to access a higher rate limit. See https://jina.ai/reader for more information."
            )
        data = {"url": url}
        
        logger.debug(f"[WEB REQUEST] JinaClient fetching: {url}")
        import time
        start_time = time.time()
        try:
            # Set a 30 second timeout for external crawling
            response = requests.post("https://r.jina.ai/", headers=headers, json=data, timeout=30.0)
            duration_ms = (time.time() - start_time) * 1000
            
            logger.debug(f"[WEB RESPONSE] JinaClient received status {response.status_code} in {duration_ms:.2f}ms for: {url}")
            response.raise_for_status()
            return response.text
        except requests.Timeout:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[TIMEOUT] JinaClient request to {url} timed out after {duration_ms:.2f}ms")
            raise
        except requests.RequestException as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[ERROR] JinaClient request to {url} failed after {duration_ms:.2f}ms: {e}")
            raise
