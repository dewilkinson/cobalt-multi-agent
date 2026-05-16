# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Agent: Scout - Web search and information retrieval tools.
# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates

# SPDX-License-Identifier: MIT

import logging
import os
import json
from typing import Any, List, Optional
from datetime import datetime

from langchain_community.tools import (
    BraveSearch,
    DuckDuckGoSearchResults,
    WikipediaQueryRun,
)
from langchain_community.tools.arxiv import ArxivQueryRun
from langchain_community.utilities import (
    ArxivAPIWrapper,
    BraveSearchWrapper,
    WikipediaAPIWrapper,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import SELECTED_SEARCH_ENGINE, SearchEngine, load_yaml_config
from src.tools.decorators import create_logged_tool
from src.tools.shared_storage import SCOUT_CONTEXT
from src.tools.tavily_search.tavily_search_results_with_images import (
    TavilySearchWithImages,
)
from src.config.database_service import research_db
from src.config.database import get_db, ResearchProject

logger = logging.getLogger(__name__)

# Agent-specific resource context (Shared by all Scout sub-modules)
_NODE_RESOURCE_CONTEXT = SCOUT_CONTEXT


# Create logged versions of the search tools
LoggedTavilySearch = create_logged_tool(TavilySearchWithImages)
LoggedDuckDuckGoSearch = create_logged_tool(DuckDuckGoSearchResults)
LoggedBraveSearch = create_logged_tool(BraveSearch)
LoggedArxivSearch = create_logged_tool(ArxivQueryRun)
LoggedWikipediaSearch = create_logged_tool(WikipediaQueryRun)


def get_search_config():
    config = load_yaml_config("conf.yaml")
    search_config = config.get("SEARCH_ENGINE", {})
    return search_config


def _ensure_default_project():
    """Ensures a default research project exists for tool persistence."""
    try:
        projects = research_db.get_all_research_projects()
        if not projects:
            project = research_db.create_research_project(
                title="VLI Default Research",
                description="Default container for automated tool-driven research artifacts.",
                tags="vli,auto-generated"
            )
            return project.id
        return projects[0].id
    except Exception as e:
        logger.error(f"Failed to ensure default project: {e}")
        return 1


def _persist_results(query: str, results: Any):
    """Internal helper to save search results to DB."""
    try:
        project_id = _ensure_default_project()
        content = str(results)
        # Create a ResearchDocument for the search result
        research_db.create_research_document(
            project_id=project_id,
            title=f"Web Search: {query[:50]}...",
            content=content,
            source_url="web_search_tool",
            document_type="search_results"
        )
        logger.info(f"[SEARCH_PERSISTENCE] Saved search results for query: {query}")
    except Exception as e:
        logger.error(f"[SEARCH_PERSISTENCE] Error saving results: {e}")


def patch_tool_with_persistence(tool_instance, engine_name="Search"):
    """Patches a search tool to persist its results to the Research Database without changing its type."""
    
    original_run = tool_instance._run
    original_arun = tool_instance._arun

    def _run_with_persistence(query: str, *args, **kwargs):
        result = original_run(query, *args, **kwargs)
        _persist_results(query, result)
        return result

    async def _arun_with_persistence(query: str, *args, **kwargs):
        try:
            @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
            async def _do_original():
                return await original_arun(query, *args, **kwargs)
            result = await _do_original()
            try:
                from src.config.vli import write_api_telemetry
                write_api_telemetry(engine_name, True, f"Query: {query[:30]}")
            except Exception: pass
            _persist_results(query, result)
            return result
        except Exception as e:
            is_tavily = engine_name.lower() == "tavily"
            
            if is_tavily:
                try:
                    from src.config.vli import write_api_telemetry
                    write_api_telemetry(engine_name, False, f"Error: {str(e)[:40]}", fallback="DuckDuckGo")
                except Exception: pass
                
                logger.warning(f"[SEARCH_FALLBACK] {engine_name} failed. Falling back to DuckDuckGo. Error: {e}")
                from langchain_community.tools import DuckDuckGoSearchResults
                @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
                async def _do_ddg():
                    ddg_tool = DuckDuckGoSearchResults(name="web_search", num_results=5)
                    return await ddg_tool._arun(query)
                result = await _do_ddg()
                _persist_results(query, result)
                return result
            else:
                try:
                    from src.config.vli import write_api_telemetry
                    write_api_telemetry(engine_name, False, f"Error: {str(e)[:40]}", fallback="None")
                except Exception: pass
                raise e

    tool_instance._run = _run_with_persistence
    tool_instance._arun = _arun_with_persistence
    
    logger.info(f"[SEARCH_HARDENING] Patched tool '{tool_instance.name}' with persistence logic.")
    return tool_instance


# Get the selected search tool
def get_web_search_tool(max_search_results: int):
    search_config = get_search_config()

    if SELECTED_SEARCH_ENGINE == SearchEngine.TAVILY.value:
        # Only get and apply include/exclude domains for Tavily
        include_domains: list[str] | None = search_config.get("include_domains", [])
        exclude_domains: list[str] | None = search_config.get("exclude_domains", [])

        logger.info(f"Tavily search configuration loaded: include_domains={include_domains}, exclude_domains={exclude_domains}")

        tool = LoggedTavilySearch(
            name="web_search",
            max_results=max_search_results,
            include_raw_content=False,
            include_images=True,
            include_image_descriptions=True,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        )
        return patch_tool_with_persistence(tool, engine_name="Tavily")
    elif SELECTED_SEARCH_ENGINE == SearchEngine.DUCKDUCKGO.value:
        tool = LoggedDuckDuckGoSearch(
            name="web_search",
            num_results=max_search_results,
        )
        return patch_tool_with_persistence(tool, engine_name="DuckDuckGo")
    elif SELECTED_SEARCH_ENGINE == SearchEngine.BRAVE_SEARCH.value:
        tool = LoggedBraveSearch(
            name="web_search",
            search_wrapper=BraveSearchWrapper(
                api_key=os.getenv("BRAVE_SEARCH_API_KEY", ""),
                search_kwargs={"count": max_search_results},
            ),
        )
        return patch_tool_with_persistence(tool, engine_name="BraveSearch")
    elif SELECTED_SEARCH_ENGINE == SearchEngine.ARXIV.value:
        tool = LoggedArxivSearch(
            name="web_search",
            api_wrapper=ArxivAPIWrapper(
                top_k_results=max_search_results,
                load_max_docs=max_search_results,
                load_all_available_meta=True,
            ),
        )
        return patch_tool_with_persistence(tool, engine_name="ArXiv")
    elif SELECTED_SEARCH_ENGINE == SearchEngine.WIKIPEDIA.value:
        wiki_lang = search_config.get("wikipedia_lang", "en")
        wiki_doc_content_chars_max = search_config.get("wikipedia_doc_content_chars_max", 4000)
        tool = LoggedWikipediaSearch(
            name="web_search",
            api_wrapper=WikipediaAPIWrapper(
                lang=wiki_lang,
                top_k_results=max_search_results,
                load_all_available_meta=True,
                doc_content_chars_max=wiki_doc_content_chars_max,
            ),
        )
        return patch_tool_with_persistence(tool, engine_name="Wikipedia")
    else:
        raise ValueError(f"Unsupported search engine: {SELECTED_SEARCH_ENGINE}")
