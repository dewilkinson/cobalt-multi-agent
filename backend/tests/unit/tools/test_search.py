# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
from unittest.mock import patch

import pytest

from src.config import SearchEngine
from src.tools.search import get_web_search_tool


class TestGetWebSearchTool:
    @patch("src.tools.search.SELECTED_SEARCH_ENGINE", SearchEngine.TAVILY.value)
    def test_get_web_search_tool_tavily(self):
        tool = get_web_search_tool(max_search_results=5)
        assert tool.name == "web_search"
        assert tool.max_results == 5
        # Current implementation has include_raw_content=False for Tavily
        assert tool.include_raw_content is False
        assert tool.include_images is True
        assert tool.include_image_descriptions is True

    @patch("src.tools.search.SELECTED_SEARCH_ENGINE", SearchEngine.DUCKDUCKGO.value)
    @patch("src.tools.search.LoggedDuckDuckGoSearch")
    def test_get_web_search_tool_duckduckgo(self, mock_ddg):
        tool = get_web_search_tool(max_search_results=3)
        assert tool == mock_ddg.return_value
        mock_ddg.assert_called_once_with(
            name="web_search",
            num_results=3,
        )

    @patch("src.tools.search.SELECTED_SEARCH_ENGINE", SearchEngine.BRAVE_SEARCH.value)
    @patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test_api_key"})
    def test_get_web_search_tool_brave(self):
        tool = get_web_search_tool(max_search_results=4)
        assert tool.name == "web_search"
        # SecretStr comparisons in Pydantic V2 require get_secret_value()
        assert tool.search_wrapper.api_key.get_secret_value() == "test_api_key"

    @patch("src.tools.search.SELECTED_SEARCH_ENGINE", SearchEngine.ARXIV.value)
    def test_get_web_search_tool_arxiv(self):
        tool = get_web_search_tool(max_search_results=2)
        assert tool.name == "web_search"
        assert tool.api_wrapper.top_k_results == 2
        assert tool.api_wrapper.load_max_docs == 2
        assert tool.api_wrapper.load_all_available_meta is True

    @patch("src.tools.search.SELECTED_SEARCH_ENGINE", "unsupported_engine")
    def test_get_web_search_tool_unsupported_engine(self):
        with pytest.raises(
            ValueError, match="Unsupported search engine: unsupported_engine"
        ):
            get_web_search_tool(max_search_results=1)

    @patch("src.tools.search.SELECTED_SEARCH_ENGINE", SearchEngine.BRAVE_SEARCH.value)
    @patch.dict(os.environ, {}, clear=True)
    def test_get_web_search_tool_brave_no_api_key(self):
        tool = get_web_search_tool(max_search_results=1)
        # SecretStr comparisons in Pydantic V2 require get_secret_value()
        assert tool.search_wrapper.api_key.get_secret_value() == ""
