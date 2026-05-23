# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import html
import re


def sanitize_content(text: str) -> str:
    """
    Sanity check and clean text content from web search results.
    Removes executable code, malicious script tags, and excessive HTML.
    """
    if not text:
        return ""

    # Remove script and style tags and their contents
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove all other HTML tags but keep content
    text = re.sub(r"<[^>]+>", "", text)

    # Unescape HTML entities
    text = html.unescape(text)

    # Remove potentially malicious patterns (basic protection)
    # e.g., javascript: protocols in what would be links
    text = re.sub(r"javascript:[^\s]*", "[REMOVED]", text, flags=re.IGNORECASE)

    # Remove malicious links/patterns like common XSS or auto-exec
    text = re.sub(r'onload\s*=\s*"[^"]*"', "", text, flags=re.IGNORECASE)

    # Normalize whitespaces
    text = re.sub(r"\s+", " ", text).strip()

    return text
