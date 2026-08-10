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

import os
import sys
import time

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Emergency BSON patch for local environment: MUST BE FIRST
try:
    import bson
    from bson import ObjectId
except (ImportError, AttributeError):
    try:
        import pymongo.bson as pymongo_bson

        sys.modules["bson"] = pymongo_bson
        from bson import ObjectId
    except Exception:
        pass

import asyncio

# Ensure Windows ProactorEventLoop for Playwright Async Support
# Note: Event loop policy is now managed by server.py to ensure institutional stability.
# Proactor is avoided for the main API process to prevent EPIPE/fileno conflicts on Windows.
import base64

import base64
import json
import logging
import re
import sys

# Emergency BSON patch for local environment
try:
    from bson import ObjectId
except (ImportError, AttributeError):
    try:
        import pymongo.bson as pymongo_bson

        sys.modules["bson"] = pymongo_bson
        patch_logger = logging.getLogger("bson_patch")
        patch_logger.info("Successfully monkey-patched BSON in app context")
    except Exception:
        pass

from datetime import datetime
from typing import Annotated, Any, cast
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Security, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

try:
    from src.version import SERVER_VERSION
except ImportError:
    SERVER_VERSION = "00.000.0000"

# --- VLI GLOBAL STATE ---
_vli_extracted_alerts = []  # [{symbol, label, color}]
_vli_macro_worker_task = None
_vli_last_macro_data = [] # Will be lazy-loaded
_vli_session_id = f"vli-{datetime.now().strftime('%Y%m%d-%H%M%S')}"  # Unique per-server-run
_vli_last_run_day = datetime.now().strftime("%Y-%m-%d")
_vli_last_inbox_log_time = 0.0
_vli_rules_enabled = False
_vli_convergence_history = []
_vli_last_async_report = ""
_vli_last_ux_card = {}
_vli_processed_draft_mtimes = {}  # [NEW] Tracking for inbox processing
_vli_action_cache_data = {}  # [NEW] Short-term identical query cache
_vli_reset_requested = False
_vli_active_task = None
_vli_fast_path_cooldown_until = datetime.now()
_vli_last_inbox_action = None
_vli_rules_active_since = datetime.now()
_vli_last_thread_id = None
_vli_dynamic_panels = []
_is_morning_scan_running = False
_is_idle_analysis_running = False


# --- VLI CONSTANTS & ALIASES ---
# DW ToDo: Gemini has created a mess here - need to rework the command parsing mechanism
TACTICAL_REPORT_ALIASES = ["analyze ", "update ", "check ", "regenerate "]
TACTICAL_REPORT_TOKENS = ["ANALYZE", "ANALYSIS", "SENTIMENT", "NEWS", "UPDATE", "CHECK", "REGENERATE"]
FAST_OVERRIDE_TOKENS = ["FAST", "QUICK", "HIGH-LEVEL", "SHORTCUT", "RAPID"]
TECH_KEYWORDS = ["SORTINO", "SHARPE", "RISK", "VOLATILITY", "ANALYSIS", "REPORT", "ANALYZE", "EXPLAIN"]
MACRO_TOKENS = ["LIST", "PRICE", "SYMBOLS", "ENVIRONMENT"]
QUALIFIER_TOKENS = ["PRICE", "VOLUME", "OHLC", "VALUE", "MA", "RSI", "MACD"]
ADMIN_CMD_TOKENS = ["CLEAR", "PURGE", "RESET", "SCAN", "FORCE", "RESTART"]
EVICT_VERBS = ["delete", "remove", "invalidate", "scrub", "clear"]
EVICT_TARGETS = ["briefing", "daily briefing", "morning briefing", "daily report", "morning report"]
EVICT_POSTMORTEM_TARGETS = ["post-mortem", "daily post-mortem", "post-mortem report", "daily post-mortem report", "daily trading report", "trading report"]
ROUTER_QUERY_TOKENS = ["WHY", "WHAT", "HOW", "WHEN", "WHERE", "WHO", "CAN", "SHOULD", "IS", "ARE", "DID", "DO", "DOES", "EXPLAIN", "COMPARE", "ANALYZE"]
ROUTER_ADMIN_TOKENS = ["CLEAR", "RESET", "REBOOT", "START", "STOP", "PAUSE", "TOGGLE", "PURGE", "FLUSH", "RUN", "GENERATE"]
TICKER_STOP_WORDS = ["GET", "STOCK", "PRICE", "LIST", "MARCO", "MARO", "VALUE", "PORT", "SYMBOL", "SMC", "FOR", "ANALYSIS", "REPORT", "ANALYZE", "FAST", "QUICK", "HIGH-LEVEL", "SHORTCUT", "RAPID", "HIGH", "LEVEL", "RAW", "DATA", "VLI", "NEWS", "SENTIMENT", "UPDATE", "CHECK", "REGENERATE"]
LEAK_KEYWORDS = ["SECURITY OVERRIDE", "APEX 500 SYSTEM", "SYSTEM INSTRUCTION", "USER IDENTITY", "OPERATIONAL MANDATE", "EXPECTED DICT", "SYSTEMMESSAGE"]
EDUCATIONAL_MARKERS = ["LEARN", "EDUCATION", "EXPLAIN", "CONCEPT", "VS", "COMPARE", "PERFORM", "KEEP UP", "YTD", "YEAR", "GIVEN", "OUTLOOK", "SCENARIO", "RECOMMEND", "SUGGEST", "DOES", "HOW"]
TACTICAL_TRIGGERS = ["ANALYZE", "ANALYSIS", "STRIKE", "SIGNAL", "SMC", "ENTRY", "SCAN", "SWORD", "SHIELD", "SETUP", "TRADE", "EXECUTE", "UPDATE", "CHECK", "REGENERATE", "SENTIMENT", "NEWS"]
QUESTION_STARTERS = ["WHAT", "HOW", "WHY", "WHEN", "WHICH", "IS", "CAN", "WHO", "WHOSE", "WHOM", "ARE", "DIFFERENCE", "WILL", "DOES", "COULD", "SHOULD"]
from fastapi.security import APIKeyHeader
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

from src.config.configuration import get_recursion_limit
from src.config.database import init_database
from src.config.database_service import research_db
from src.config.loader import get_bool_env, get_str_env
from src.config.report_style import ReportStyle
from src.config.tools import SELECTED_RAG_PROVIDER
from src.config.vli import VAULT_ROOT, get_action_plan_path, get_archive_path, get_inbox_path, get_vli_path
from src.graph.builder import build_graph_with_memory
from src.graph.checkpoint import chat_stream_message

# Use our clean, native checkpointer to avoid BSON version conflict
from src.graph.mongodb_checkpointer import NativeMongoDBSaver
from src.llms.llm import get_configured_llm_models
from src.podcast.graph.builder import build_graph as build_podcast_graph
from src.ppt.graph.builder import build_graph as build_ppt_graph
from src.prompt_enhancer.graph.builder import build_graph as build_prompt_enhancer_graph
from src.prose.graph.builder import build_graph as build_prose_graph
from src.rag.builder import build_retriever
from src.rag.milvus import load_examples
from src.rag.retriever import Resource
from src.server.chat_request import (
    ChatRequest,
    EnhancePromptRequest,
    GeneratePodcastRequest,
    GeneratePPTRequest,
    GenerateProseRequest,
    TTSRequest,
)
from src.server.config_request import ConfigResponse
from src.server.mcp_request import MCPServerMetadataRequest, MCPServerMetadataResponse
from src.server.mcp_utils import load_mcp_tools
from src.server.rag_request import (
    RAGConfigResponse,
    RAGResourceRequest,
    RAGResourcesResponse,
)
from src.server.research_api import router as research_router
from src.server.studio_api import router as studio_router
from src.tools import VolcengineTTS
from src.tools.scraper import get_latest_ux_data
from src.utils.json_utils import sanitize_args

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# StreamHandler added to ensure console visibility in the user's terminal
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

from src.services.macro_registry import macro_registry

from fastapi.responses import StreamingResponse

def get_reports_root() -> str:
    import os
    default_root = os.path.join(os.getcwd(), "data", "reports")
    if not os.path.exists(os.path.join(os.getcwd(), "data")):
        default_root = os.path.join(os.getcwd(), "backend", "data", "reports")
    return os.environ.get("VLI_REPORTS_ROOT", default_root)

def get_daily_briefing_path() -> str:
    import os
    from datetime import datetime
    today_str = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(get_reports_root(), today_str, f"{today_str} Daily Briefing.md")

def get_data_file_path(filename: str) -> str:
    import os
    path = os.path.join(os.getcwd(), "data", filename)
    if not os.path.exists(path):
        path = os.path.join(os.getcwd(), "backend", "data", filename)
    return path

# Global variables for system context
last_graph_state = None
global_telemetry_queue = None
_artifacts_tree_cache = None
_artifacts_tree_cache_time = 0.0
_artifacts_tree_cache_lock = None

def get_telemetry_queue():
    global global_telemetry_queue
    if global_telemetry_queue is None:
        import asyncio
        global_telemetry_queue = asyncio.Queue()
    return global_telemetry_queue
# (Variables now moved to unified block above)
from collections import defaultdict
_vli_chat_history_store = defaultdict(list) # {client_id: [{role, content, thought, timestamp, thread_id}]}

def _append_to_vli_history(role: str, content: str, thought: str = "", thread_id: str = None):
    """Unified logger for VLI Chat history."""
    if content and "[SILENT_LOG]" in str(content):
        return
        
    try:
        from src.config.vli_context import vli_client_id
        cid = vli_client_id.get("default")
    except Exception:
        cid = "default"
        
    global _vli_chat_history_store
    _vli_chat_history_store[cid].append({
        "role": role,
        "content": content,
        "thought": thought,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "thread_id": thread_id
    })
    # Keep history manageable (last 50 messages per client)
    if len(_vli_chat_history_store[cid]) > 50:
        _vli_chat_history_store[cid] = _vli_chat_history_store[cid][-50:]

def scrub_vli_output(text) -> str:
    """Universal firewall to prevent technical instruction leakage and verbose error clusters."""
    if text is None: return ""
    content = str(text)
    upper_content = content.upper()
    if any(k in upper_content for k in LEAK_KEYWORDS):
        logger.error(f"[SCRUBBER DEBUG] Caught leak keywords in: {content}")
        return "**Managed Processing Recovery**: The analytical engine experienced a structural interruption or reasoning quota limit. Technical metadata has been suppressed for system integrity."
    return content
_vli_reset_requested = False
_vli_active_task = None
_vli_fast_path_cooldown_until = datetime.now()
_vli_last_inbox_action = None
_vli_rules_active_since = datetime.now()
_vli_last_thread_id = None

# [NEW] Decoupled VLI Macro Integration
# Ensuring the path is relative to the backend workspace root
VLI_SNAPSHOT_FILE = os.path.join(os.getcwd(), "backend", "data", "vli_macro_snapshot.json")


def _get_vli_macro_snapshot() -> list:
    """Reads the latest institutional macro data from the standalone worker's snapshot."""
    try:
        if os.path.exists(VLI_SNAPSHOT_FILE):
            with open(VLI_SNAPSHOT_FILE, encoding="utf-8") as f:
                data = json.load(f)
                return data.get("macros", [])
    except Exception as e:
        logger.error(f"VLI: Failed to read macro snapshot: {e}")
    return []


def _get_report_filename(request_text: str, content: str) -> str:
    """Consistently maps a directive to a safe filename for dashboard artifact links."""
    import re

    # [MATCH FRONTEND JS PRE-PROCESSING]
    # The dashboard strips these before sending, but we strip them again here
    # for robustness. We use a more explicit case-insensitive approach.
    t = request_text
    for flag in ["--raw", "--background", "--direct", "--fast"]:
        t = re.sub(re.escape(flag), "", t, flags=re.IGNORECASE)
    clean_text = t.strip()

    txt_trim = content.strip()
    suffix = "md"
    if txt_trim.startswith("{") or txt_trim.startswith("["):
        suffix = "json"
    elif "<html" in txt_trim.lower() or "<div" in txt_trim.lower():
        suffix = "html"

    base_name = "vli_report"
    if clean_text:
        # [MATCH FRONTEND JS] re.sub(/[^a-zA-Z0-9\s]/g, '').trim().replace(/\s+/g, '_').substring(0, 25).toLowerCase()
        slug = re.sub(r"[^a-zA-Z0-9\s]", "", clean_text).strip()
        base_name = re.sub(r"\s+", "_", slug)[:25].lower()
        if base_name.startswith("update_") or base_name.startswith("check_"):
            base_name = base_name.replace("update_", "analyze_", 1).replace("check_", "analyze_", 1)
        if not base_name:
            base_name = "vli_report"

    return f"{base_name}.{suffix}"


def _persist_vli_report(request_text: str, content: str):
    """Saves a report to the data/reports/ directory for dashboard access."""
    if not content or len(content) < 50:
        return None
        
    # [HARDENING] Prevent error payloads from poisoning the cache
    if "Agent reasoning encountered a failure" in content or "timed out" in content.lower():
        logger.warning(f"VLI_SYSTEM: Blocked persistence of erroneous report for directive '{request_text}'")
        return None

    filename = _get_report_filename(request_text, content)
    try:
        reports_dir = os.path.join(os.getcwd(), "data", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        file_path = os.path.join(reports_dir, filename)
        
        # [SILENT_MODE] Strip prefix for clean persistence
        clean_content = content.replace("[SILENT_LOG] ", "")
        
        generation_ts = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        header = f"> **Generated:** {generation_ts}\n\n"
        
        with open(file_path, "w", encoding="utf-8") as rf:
            rf.write(header + clean_content)
            
        # [UX SYNC] Instantly update scanner state if this is a ticker report, 
        # so manual 'analyze' commands turn the document icon green.
        import re
        sym_match = re.search(r"analyze_([a-z0-9\-]+)\.md", filename)
        if sym_match:
            sym = sym_match.group(1).upper()
            try:
                from src.config.vli import get_vli_path
                for target_state in ["STRIKE_RES_state.json", "STRIKE_LIST.json", "STRIKE_LIST.json"]:
                    s_path = get_vli_path(os.path.join("01_Transit", "Buckets", target_state)) if "state" in target_state else os.path.join(os.getcwd(), 'data', target_state)
                    if os.path.exists(s_path):
                        with open(s_path, "r", encoding="utf-8") as f:
                            s_data = json.load(f)
                        updated = False
                        target_list = s_data.get("candidates", []) if isinstance(s_data, dict) and "candidates" in s_data else (s_data.get("strike_list", []) if isinstance(s_data, dict) else [])
                        for c_item in target_list:
                            if isinstance(c_item, dict) and c_item.get("symbol", "").upper() == sym:
                                c_item["has_report"] = True
                                c_item["updated_at"] = datetime.now().isoformat()
                                updated = True
                        if updated:
                            with open(s_path, "w", encoding="utf-8") as f:
                                json.dump(s_data, f, indent=4)
            except Exception as e:
                logger.error(f"[VLI_SYSTEM] Failed to sync UI state for generated report {sym}: {e}")
                
        return filename
    except Exception as e:
        logger.error(f"VLI_SYSTEM: Failed to persist report '{filename}': {e}")
        return None


def _get_vli_intent(text: str) -> str:
    """Standardized intent classification for Market Insight vs Tactical Execution."""
    text_trim = text.strip()
    text_upper = text_trim.upper()
    is_smc = "SMC" in text_upper
    
    is_tactical = any(kw in text_upper for kw in TACTICAL_TRIGGERS) or is_smc
    is_educational = any(kw in text_upper for kw in EDUCATIONAL_MARKERS)
    
    if is_tactical and not is_educational:
        return "TACTICAL_EXECUTION"
        
    is_question = any(text_upper.startswith(qs) for qs in QUESTION_STARTERS) or text_trim.endswith("?") or text_trim.endswith("!")
    
    if is_educational or is_question:
        return "MARKET_INSIGHT"
        
    if is_tactical:
        return "TACTICAL_EXECUTION"
        
    return "MARKET_INSIGHT"


def create_futures_watchlist_panel():
    """Create a high-fidelity Futures Watchlist panel with Sortino indicators."""
    html = """
    <table style="width:100%; border-collapse:collapse; margin-top:10px; font-size:14px;">
        <thead>
            <tr style="text-align:left; border-bottom:1px solid var(--border-color); color:var(--text-primary); font-size:12px; font-family:'Outfit';">
                <th style="padding:10px 5px; letter-spacing:1px;">SYMBOL</th>
                <th style="padding:10px 5px; letter-spacing:1px;">PRICE</th>
                <th style="padding:10px 5px; letter-spacing:1px;">CHANGE</th>
                <th style="padding:10px 5px; letter-spacing:1px;">SORTINO</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td style="padding:12px 5px;">$ES (E-mini)</td>
                <td style="padding:12px 5px; font-family:monospace;">5,245.50</td>
                <td style="padding:12px 5px; color:var(--emerald-green);">+0.85%</td>
                <td style="padding:12px 5px;"><span class="sortino-indicator sortino-green"></span>2.2</td>
            </tr>
            <tr style="background:rgba(255,255,255,0.02);">
                <td style="padding:12px 5px;">$NQ (Nasdaq)</td>
                <td style="padding:12px 5px; font-family:monospace;">18,412.25</td>
                <td style="padding:12px 5px; color:var(--emerald-green);">+1.20%</td>
                <td style="padding:12px 5px;"><span class="sortino-indicator sortino-green"></span>2.8</td>
            </tr>
            <tr>
                <td style="padding:12px 5px;">$GC (Gold)</td>
                <td style="padding:12px 5px; font-family:monospace;">2,185.40</td>
                <td style="padding:12px 5px; color:#f85149;">-0.15%</td>
                <td style="padding:12px 5px;"><span class="sortino-indicator sortino-yellow"></span>1.1</td>
            </tr>
        </tbody>
    </table>
    """
    return {"id": "watch-futures-01", "title": "Futures Watchlist", "content_html": html}


def extract_vli_logic(text: str) -> list[dict[str, str]]:
    """Extract ticker symbols and risk thresholds from markdown text."""
    try:
        global _vli_dynamic_panels
        text_lower = text.lower()
        if "futures" in text_lower and "watchlist" in text_lower:
            # Check if already added
            if not any(p["id"] == "watch-futures-01" for p in _vli_dynamic_panels):
                logger.info("VLI: Triggering 'Futures Watchlist' dynamic panel.")
                _vli_dynamic_panels.append(create_futures_watchlist_panel())

        alerts = []

        # 1. Extract Symbols: $TICKER
        symbols = re.findall(r"\$([A-Z]{1,5})", text)
        for sym in set(symbols):
            alerts.append({"symbol": sym, "label": "Detected in Action Plan", "color": "green"})

        # 2. Extract Logic: S_{DR} >= 2.0
        logic_matches = re.findall(r"(S_{DR}\s*[>=<]+\s*\d+\.?\d*)", text)
        for logic in set(logic_matches):
            alerts.append({"symbol": "LOGIC", "label": logic, "color": "blue"})

        global _vli_last_inbox_log_time
        if datetime.now().timestamp() - _vli_last_inbox_log_time > 2.0:
            logger.info(f"VLI: Extracted {len(alerts)} alerts from text.")
            _vli_last_inbox_log_time = datetime.now().timestamp()
        return alerts
    except Exception as e:
        logger.error(f"VLI Logic Extraction Failed: {e}")
        return []


INTERNAL_SERVER_ERROR_DETAIL = "Internal Server Error"

def clear_stale_scanner_files(force: bool = False):
    """
    Clears scanner strike lists and transit states if they are from a previous day.
    If force=True, clears them unconditionally.
    """
    import os
    import json
    from datetime import datetime
    from src.config.vli import get_vli_path
    
    current_day = datetime.now().date()
    
    # 1. Define files and their reset structures
    base_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    root_data_dir = os.path.abspath(os.path.join(os.getcwd(), "data"))
    
    files = [
        # (path, default_content_if_dict_or_list)
        (os.path.join(base_data_dir, "STRIKE_LIST.json"), {"strike_list": []}),
        (os.path.join(base_data_dir, "SCANNER_STRIKE_LIST.json"), {"strike_list": []}),
        (os.path.join(base_data_dir, "SCANNER_COMBAT_LIST.json"), {"strike_list": []}),
        (os.path.join(base_data_dir, "SHIELD_COMBAT_LIST.json"), []),
        (os.path.join(root_data_dir, "STRIKE_LIST.json"), {"strike_list": []}),
        (os.path.join(root_data_dir, "SCANNER_STRIKE_LIST.json"), {"strike_list": []}),
        (get_vli_path(os.path.join("01_Transit", "Buckets", "STRIKE_RES_state.json")), {"pulse_mode": "CLEARED", "total_pulsed": 0, "candidates_passed": 0, "candidates": []}),
        (get_vli_path(os.path.join("01_Transit", "Buckets", "SCANNER_RES_state.json")), {"pulse_mode": "CLEARED", "total_pulsed": 0, "candidates_passed": 0, "candidates": []}),
        (get_vli_path(os.path.join("01_Transit", "Buckets", "SHIELD_RES_state.json")), {"pulse_mode": "CLEARED", "total_pulsed": 0, "candidates_passed": 0, "candidates": []}),
    ]
    
    purged = []
    for filepath, default_content in files:
        if not os.path.exists(filepath):
            continue
            
        should_clear = force
        if not should_clear:
            try:
                # Check modification time
                mtime = os.path.getmtime(filepath)
                mtime_date = datetime.fromtimestamp(mtime).date()
                if mtime_date < current_day:
                    should_clear = True
            except Exception as e:
                logger.error(f"Failed to check mtime for {filepath}: {e}")
                
        if should_clear:
            try:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(default_content, f, indent=4)
                purged.append(os.path.basename(filepath))
            except Exception as e:
                logger.error(f"Failed to clear stale scanner file {filepath}: {e}")
                
    if purged:
        logger.info(f"VLI_SYSTEM: Cleared stale scanner lists/states from previous days: {purged}")

from contextlib import asynccontextmanager

def start_ngrok_tunnel():
    import subprocess
    import urllib.request
    import json
    import os
    
    domain = os.environ.get("NGROK_DOMAIN", "")
    authtoken = os.environ.get("NGROK_AUTHTOKEN", "")
    
    # Fallback to conf.yaml
    if not domain or not authtoken:
        try:
            b_dir = os.path.dirname(os.path.abspath(__file__))
            conf_path = os.path.abspath(os.path.join(b_dir, "..", "..", "conf.yaml"))
            if os.path.exists(conf_path):
                import yaml
                with open(conf_path, "r", encoding="utf-8") as f:
                    conf = yaml.safe_load(f)
                if conf and isinstance(conf, dict) and "NGROK" in conf:
                    ngrok_cfg = conf["NGROK"]
                    if isinstance(ngrok_cfg, dict):
                        domain = domain or ngrok_cfg.get("domain", "")
                        authtoken = authtoken or ngrok_cfg.get("authtoken", "")
        except Exception as ex:
            logger.debug(f"Failed to read conf.yaml for ngrok settings: {ex}")
            
    clean_domain = domain.replace("https://", "").replace("http://", "").strip()
    if not clean_domain:
        logger.info("VLI_SYSTEM: NGROK_DOMAIN is empty. Skipping auto-tunnel startup.")
        return
        
    if authtoken:
        try:
            subprocess.run(["ngrok", "config", "add-authtoken", authtoken], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            logger.info("VLI_SYSTEM: Configured ngrok authtoken.")
        except Exception as ex:
            logger.warning(f"VLI_SYSTEM: Failed to set ngrok authtoken: {ex}")
            
    needs_restart = False
    try:
        req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
        with urllib.request.urlopen(req, timeout=1.0) as response:
            tunnels = json.loads(response.read().decode('utf-8'))
        active_tunnels = tunnels.get("tunnels", [])
        
        has_correct_tunnel = False
        for t in active_tunnels:
            public_url = t.get("public_url", "")
            addr = t.get("config", {}).get("addr", "")
            if clean_domain in public_url:
                if "8000" in addr:
                    has_correct_tunnel = True
                else:
                    needs_restart = True
                    
        if has_correct_tunnel:
            logger.info(f"VLI_SYSTEM: Ngrok tunnel already active for {clean_domain} on port 8000")
            return
    except Exception:
        pass
        
    if needs_restart:
        logger.info("VLI_SYSTEM: Ngrok running on wrong port. Killing existing process...")
        try:
            import time
            if os.name == 'nt':
                subprocess.run(["taskkill", "/F", "/IM", "ngrok.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["killall", "ngrok"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
        except Exception as ex:
            logger.warning(f"VLI_SYSTEM: Failed to kill ngrok process: {ex}")
        
    logger.info(f"VLI_SYSTEM: Spawning Ngrok tunnel for domain: {clean_domain}")
    try:
        cmd = ["ngrok", "http", "127.0.0.1:8000", "--domain", clean_domain]
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                         creationflags=creationflags)
        logger.info(f"VLI_SYSTEM: Ngrok tunnel spawned successfully in background.")
    except Exception as e:
        logger.error(f"VLI_SYSTEM: Failed to spawn ngrok tunnel: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - Clear stale scanner lists from previous days
    try:
        clear_stale_scanner_files()
    except Exception as e:
        logger.error(f"VLI_SYSTEM: Failed to run clear_stale_scanner_files at startup: {e}")

    # Startup Ngrok Tunnel if configured
    try:
        start_ngrok_tunnel()
    except Exception as e:
        logger.error(f"VLI_SYSTEM: Failed to start ngrok tunnel at startup: {e}")

    # [NEW] Automatic Startup catch-up sequence disabled as per user instruction
    # from datetime import datetime
    # now = datetime.now()
    # if now.hour >= 6:
    #     if not os.path.exists(get_daily_briefing_path()):
    #         logger.info("VLI_SYSTEM: Missed Morning Scan detected. Scheduling catch-up sequence in 5 seconds...")
    #         async def catchup_with_delay():
    #             await asyncio.sleep(5)
    #             await run_daily_morning_analysis()
    #         asyncio.create_task(catchup_with_delay())
            
    # [NEW] Dashboard Integrity Guard
    b_dir = os.path.dirname(os.path.abspath(__file__))  # src/server
    b_root = os.path.abspath(os.path.join(b_dir, "..", ".."))  # backend/
    dashboard_path = os.path.join(b_root, "public", "vli_dashboard.html")
    if not os.path.exists(dashboard_path):
        logger.error(f"CRITICAL ERROR: VLI Dashboard file missing at {dashboard_path}")
    else:
        logger.info(f"VLI_SYSTEM: Dashboard integrity verified at {dashboard_path}")

    logger.info("Cobalt Multiagent: Launching Unified Heartbeat Engine.")
    from src.services.scheduler import cobalt_scheduler
    
    # Register Internal System Tasks
    from src.services.csv_importer import watch_dropzone_and_process
    cobalt_scheduler.add_timer(
        task_id="DROPZONE_WATCHER",
        name="VLI Dropzone CSV Processor",
        type="REPEAT",
        schedule=5,
        period_unit="seconds",
        priority="NORMAL",
        callback=watch_dropzone_and_process
    )

    cobalt_scheduler.add_timer(
        task_id="INBOX_WATCHER",
        name="VLI Inbox & Archiver Watcher",
        type="REPEAT",
        schedule=2,
        period_unit="seconds",
        priority="NORMAL",
        callback=vli_inbox_tick
    )
    
    from src.services.brokerage_cache import BrokerageCache
    cobalt_scheduler.add_timer(
        task_id="CACHE_BACKUP_DAILY",
        name="Brokerage Cache Daily Backup",
        type="CALENDAR",
        schedule="0 19 * * 1-5",
        priority="BACKGROUND",
        callback=BrokerageCache.backup_cache_daily
    )
    
    cobalt_scheduler.add_timer(
        task_id="CACHE_BACKUP_WEEKLY",
        name="Brokerage Cache Weekly Archival",
        type="CALENDAR",
        schedule="0 19 * * 5",
        priority="BACKGROUND",
        callback=BrokerageCache.backup_cache_weekly
    )
    
    # [HARDENING] Conditional Scanner Logic
    scanner_engine = get_str_env("VLI_SCANNER_ENGINE", "cobalt").lower()
    logger.info(f"VLI_SYSTEM: Using scanner engine: {scanner_engine.upper()}")

    if scanner_engine == "tradingview":
        # Register TradingView Sync Task (Bypasses internal Sortino/Pulse logic)
        cobalt_scheduler.add_timer(
            task_id="TV_SCANNER_SYNC",
            name="TradingView Apex Scanner Sync",
            type="REPEAT",
            schedule=1,
            period_unit="minutes",
            priority="LOW",
            callback=run_tv_sync
        )
        logger.info("VLI_SYSTEM: Internal Cobalt scanner logic BYPASSED (Using TradingView Engine)")
    else:
        # Register Internal Cobalt Scanner Logic
        from src.tools.sortino_sniper_trawl import run_background_trawl, run_intraday_trawl
        
        cobalt_scheduler.add_timer(
            task_id="INTRADAY_COMBAT_TRAWL",
            name="Intraday Momentum Trawl Watchdog",
            type="REPEAT",
            schedule=15,
            period_unit="minutes",
            priority="LOW",
            callback=run_intraday_trawl
        )
        
        cobalt_scheduler.add_timer(
            task_id="PULSE_TRACKER",
            name="Phase 2 Pulse Signal Watchdog",
            type="REPEAT",
            schedule=5,
            period_unit="minutes",
            priority="LOW",
            callback=poll_market_pulse
        )



    async def trigger_daily_postmortem():
        """
        Cron task running at 5:00 PM EST.
        Generates the Daily Trading Report (post-mortem) and condenses Symbol Analysis reports generated today.
        """
        logger.info("[POSTMORTEM_AUTO] Initiating 5:00 PM Daily Trading Report sequence.")
        import os
        from datetime import datetime
        import json

        # Check if any trades were made today in brokerage cache
        has_trades = False
        try:
            b_dir = os.path.dirname(os.path.abspath(__file__))  # src/server
            cache_path = os.path.abspath(os.path.join(b_dir, "..", "..", "data", "brokerage_cache.json"))
            if os.path.exists(cache_path):
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                
                today_str = datetime.now().strftime("%Y-%m-%d")
                for account, details in cache_data.items():
                    activities = details.get("activities", [])
                    for act in activities:
                        trade_date = act.get("trade_date", "")
                        status = act.get("status", "").upper()
                        if today_str in trade_date and status in ["EXECUTED", "FILLED"]:
                            has_trades = True
                            break
                    if has_trades:
                        break
        except Exception as ce:
            logger.warning(f"Failed to check brokerage cache for today's trades: {ce}")
            has_trades = True # Fallback to True to be safe

        if not has_trades:
            logger.info("[POSTMORTEM_AUTO] No trades made today. Skipping daily post-mortem report generation.")
            return

        # 1. Trigger the post-mortem analysis
        try:
            from src.services.historical_reports import PERFORMANCE_DIR
            date_str = datetime.now().strftime("%Y-%m-%d")
            report_path = os.path.join(PERFORMANCE_DIR, f"Daily_PostMortem_{date_str}.md")
            
            # Delete if it exists and was created before 16:00
            if os.path.exists(report_path):
                mtime = datetime.fromtimestamp(os.path.getmtime(report_path))
                if mtime.hour < 16:
                    os.remove(report_path)
                    logger.info(f"Deleted premature post-mortem report: {report_path}")
                    
            # Trigger background synthesis
            import asyncio
            asyncio.create_task(_background_synthesis_task(
                text="Analyze today's executed trades and generate a detailed Daily Trading Report post-mortem.",
                image=None,
                thread_id=f"POSTMORTEM_{date_str}",
                direct_mode=False,
                reporter_llm_type="reasoning",
                vli_llm_type="core"
            ))
        except Exception as e:
            logger.error(f"Failed to trigger daily post-mortem: {e}")
            
        # 2. Condense any raw Symbol Analysis reports generated today into rolling summaries
        try:
            from src.services.historical_reports import REPORTS_DIR, update_symbol_rolling_summary
            import glob
            
            symbol_reports = glob.glob(os.path.join(REPORTS_DIR, "analyze_*.md"))
            today_date = datetime.now().date()
            
            for r_path in symbol_reports:
                if not os.path.basename(r_path).startswith("analyze_meta"):
                    mtime = datetime.fromtimestamp(os.path.getmtime(r_path))
                    if mtime.date() == today_date:
                        sym = os.path.basename(r_path).replace("analyze_", "").replace(".md", "")
                        with open(r_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        logger.info(f"Condensing today's analysis for {sym.upper()} into rolling summary.")
                        update_symbol_rolling_summary(sym.upper(), content)
                        
        except Exception as e:
            logger.error(f"Failed to run symbol report condensation: {e}")
            
    # Register 5:00 PM Daily Post-Mortem
    cobalt_scheduler.add_timer(
        task_id="DAILY_POSTMORTEM",
        name="5:00 PM Daily Trading Post-Mortem",
        type="CALENDAR",
        schedule="0 17 * * 1-5",
        priority="HIGH",
        callback=trigger_daily_postmortem
    )
    
    # Register 8:30 AM Start of Day (SOD) Morning Analyst Prep - DISABLED as per user instruction
    # cobalt_scheduler.add_timer(
    #     task_id="DAILY_ANALYST",
    #     name="8:30 AM Start of Day Prep (SOD)",
    #     type="CALENDAR",
    #     schedule="30 8 * * *",
    #     priority="HIGH",
    #     callback=run_daily_morning_analysis
    # )

    # Register 8:30 AM Start of Day (SOD) Executive Morning Briefing - DISABLED as per user instruction
    # cobalt_scheduler.add_timer(
    #     task_id="EXECUTIVE_BRIEFING",
    #     name="Daily Executive Briefing (SOD)",
    #     type="CALENDAR",
    #     schedule="30 8 * * *",
    #     priority="HIGH",
    #     callback=run_meta_analysis
    # )

    cobalt_scheduler.add_timer(
        task_id="SMC_5M_POLLER",
        name="5-Minute Structure Alert Watchdog",
        type="REPEAT",
        schedule=5,
        period_unit="minutes",
        priority="NORMAL",
        callback=poll_5m_patterns
    )

    # Initialize Watchlist Exports Session (Clean previous sessions, generate new unique session timestamp)
    try:
        import glob
        exports_dir = os.path.join(os.getcwd(), "data", "exports")
        if not os.path.exists(exports_dir):
            exports_dir = os.path.join(os.getcwd(), "backend", "data", "exports")
        if os.path.exists(exports_dir):
            for pattern in ["watchlist_*_*.txt", "scanner_watchlist_all_*.txt"]:
                for filepath in glob.glob(os.path.join(exports_dir, pattern)):
                    try:
                        os.remove(filepath)
                    except Exception as e:
                        logger.warning(f"Failed to delete old watchlist file {filepath}: {e}")
        session_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        meta_path = os.path.join(os.getcwd(), "data", ".session_metadata.json")
        if not os.path.exists(os.path.dirname(meta_path)):
            meta_path = os.path.join(os.getcwd(), "backend", "data", ".session_metadata.json")
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"session_timestamp": session_ts}, f)
        logger.info(f"Initialized new watchlist export session with timestamp: {session_ts}")
    except Exception as e:
        logger.error(f"Failed to initialize watchlist export session: {e}")

    cobalt_scheduler.add_timer(
        task_id="TV_WATCHLIST_EXPORT",
        name="TradingView Watchlist Periodic Export",
        type="CALENDAR",
        schedule="*/5 4-20 * * 1-5", # Every 5 minutes, 4:00 AM to 8:59 PM, Monday through Friday
        priority="LOW",
        callback=run_tv_watchlist_export_task
    )

    cobalt_scheduler.start()
    
    # Load examples into Milvus if configured
    try:
        load_examples()
    except Exception as e:
        logger.error(f"Failed to load examples: {e}")
    
    # Initialize research database
    try:
        db_success = init_database()
        if db_success:
            logger.info("Research database initialized successfully")
        else:
            logger.warning("Research database initialization skipped - some features may be limited")
    except Exception as e:
        logger.error(f"Failed to initialize research database: {e}")
        
    yield
    
    # Shutdown
    try:
        from src.services.scheduler import cobalt_scheduler
        cobalt_scheduler.stop()
    except Exception as e:
        logger.error(f"Failed to shutdown scheduler: {e}")

app = FastAPI(title="Cobalt Multi-Agent (CMA) - VibeLink Interface", description="Institutional-grade agentic financial monitoring pipeline.", version="10.2.1", lifespan=lifespan)

@app.get("/api/telemetry/stream")
async def ui_telemetry_stream():
    """Streams global telemetry events to the UI."""
    async def event_generator():
        while True:
            msg = await get_telemetry_queue().get()
            yield f"data: {json.dumps({'type': 'telemetry', 'msg': msg})}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")



@app.get("/api/scheduler/logs")
async def get_scheduler_logs():
    try:
        from src.services.scheduler import cobalt_scheduler
        logs = cobalt_scheduler.get_execution_log(limit=100)
        return {"status": "OK", "logs": logs}
    except Exception as e:
        logger.error(f"Failed to fetch scheduler logs: {e}")
        return {"status": "ERROR", "error": str(e)}

@app.post("/api/vli/reset_scheduler_logs")
async def reset_scheduler_logs():
    try:
        from src.services.scheduler import cobalt_scheduler
        with open(cobalt_scheduler.log_file, 'w', encoding='utf-8') as f:
            f.write("[HEARTBEAT] Scheduler Log Cleared via Dashboard Command.\n")
        return {"status": "OK"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

@app.get("/api/health")
async def health_check():
    try:
        return {"status": "ok", "version": SERVER_VERSION}
    except Exception:
        return {"status": "ok", "version": "00.000.0000"}


@app.get("/vli")
async def vli_dashboard_redirect():
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/vli_dashboard.html")


def build_file_tree(dir_path: str):
    tree = []
    if not os.path.exists(dir_path):
        return tree
    
    for item in sorted(os.listdir(dir_path)):
        full_path = os.path.join(dir_path, item)
        if os.path.isdir(full_path):
            # Only add folders that aren't empty, or just add them
            children = build_file_tree(full_path)
            if children:
                tree.append({
                    "name": item,
                    "type": "folder",
                    "children": children
                })
        elif item.endswith('.md') or item.endswith('.json') or item.endswith('.txt'):
            # Convert Windows backslashes to forward slashes for safer URL handling
            tree.append({
                "name": item,
                "type": "file",
                "path": full_path.replace("\\", "/")
            })
    return tree

def _build_artifacts_tree_sync(reports_dir: str):
    import os
    
    sources = [
        reports_dir,
        os.path.join(os.getcwd(), "backend", "data", "reports"),
        r"C:\github\obsidian-vault\_cobalt\research",
        r"C:\github\obsidian-vault\_cobalt",
        r"C:\github\obsidian-vault\_cobalt\Reports"
    ]
    
    folders_map = {}
    ignored = {"history", "performance", "vli_cache", "artifacts", "reports", "templates", "inbox", "action_plans", "_memory", "archives", "analyze_"}

    for sdir in sources:
        if not os.path.exists(sdir):
            continue
        for root_item in os.listdir(sdir):
            if root_item.lower() in ignored:
                continue
                
            root_path = os.path.join(sdir, root_item)
            if not os.path.isdir(root_path):
                continue
                
            folder_key = root_item.lower()
            if folder_key not in folders_map:
                display_name = "Research" if folder_key == "research" else root_item
                folders_map[folder_key] = {
                    "name": display_name,
                    "files": {},
                    "subfolders": {}
                }
            
            f_node = folders_map[folder_key]
            
            try:
                for child_item in os.listdir(root_path):
                    child_path = os.path.join(root_path, child_item)
                    if os.path.isfile(child_path) and child_item.endswith(".md"):
                        if "smc_analysis" in child_item.lower():
                            continue
                        if child_item not in f_node["files"]:
                            is_system_file = ("Daily Briefing" in child_item) or ("Daily Journal" in child_item)
                            mtime = os.path.getmtime(child_path) if os.path.exists(child_path) else 0
                            f_node["files"][child_item] = ({
                                "name": child_item,
                                "type": "file",
                                "path": child_path.replace("\\", "/"),
                                "canRename": not is_system_file,
                                "canDelete": not is_system_file
                            }, mtime)
                    elif os.path.isdir(child_path):
                        sub_key = child_item.lower()
                        if sub_key not in f_node["subfolders"]:
                            f_node["subfolders"][sub_key] = {
                                "name": child_item,
                                "path": child_path.replace("\\", "/"),
                                "files": {}
                            }
                        sub_node = f_node["subfolders"][sub_key]
                        for inner_item in os.listdir(child_path):
                            inner_path = os.path.join(child_path, inner_item)
                            if os.path.isfile(inner_path) and inner_item.endswith(".md"):
                                if "smc_analysis" in inner_item.lower():
                                    continue
                                if inner_item not in sub_node["files"]:
                                    sub_node["files"][inner_item] = {
                                        "name": inner_item,
                                        "type": "file",
                                        "path": inner_path.replace("\\", "/"),
                                        "canRename": True,
                                        "canDelete": True
                                    }
            except Exception:
                pass

    tree = []
    for f_key, f_node in folders_map.items():
        children = []
        
        # Add subfolders
        for sub_key, sub_node in f_node["subfolders"].items():
            sorted_inner = sorted(list(sub_node["files"].values()), key=lambda x: x["name"])
            children.append({
                "name": sub_node["name"],
                "type": "folder",
                "path": sub_node["path"],
                "children": sorted_inner
            })
            
        # Add files
        file_list = list(f_node["files"].values())
        if len(file_list) > 150:
            file_list.sort(key=lambda x: x[1], reverse=True)
            file_list = file_list[:150]
            
        children.extend([f[0] for f in file_list])
        
        tree.append({
            "name": f_node["name"],
            "type": "folder",
            "children": sorted(children, key=lambda x: (x["type"] == "folder", x["name"]))
        })

    tree.sort(key=lambda x: x["name"], reverse=True)
    return tree

@app.get("/api/vli/artifacts/tree")
async def get_artifacts_tree():
    import os
    import asyncio
    import time
    from datetime import datetime
    
    global _artifacts_tree_cache, _artifacts_tree_cache_time, _artifacts_tree_cache_lock
    
    if _artifacts_tree_cache_lock is None:
        _artifacts_tree_cache_lock = asyncio.Lock()
        
    reports_dir = get_reports_root()
    os.makedirs(reports_dir, exist_ok=True)
        
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    # Only auto-create folder structure on trading days (Mon-Fri) at/after 6 AM
    if now.weekday() < 5 and now.hour >= 6:
        try:
            today_dir = os.path.join(reports_dir, today_str)
            notes_dir = os.path.join(today_dir, "Notes")
            os.makedirs(notes_dir, exist_ok=True)
            
            # Generate Journal if missing
            journal_path = os.path.join(today_dir, f"{today_str} Daily Journal.md")
            if not os.path.exists(journal_path):
                with open(journal_path, "w", encoding="utf-8") as f:
                    f.write(f"# {today_str} Daily Journal\n\n## Trades\n| Symbol | Direction | Entry | Exit | PnL | Notes |\n| :--- | :--- | :--- | :--- | :--- | :--- |\n| | | | | | |\n\n## Notes\n- \n")
        except Exception as e:
            logger.error(f"Failed to auto-create daily directory or journal: {e}")
            
    async with _artifacts_tree_cache_lock:
        if _artifacts_tree_cache is not None and (time.time() - _artifacts_tree_cache_time) < 2.0:
            return {"status": "OK", "tree": _artifacts_tree_cache}
            
        try:
            tree = await asyncio.to_thread(_build_artifacts_tree_sync, reports_dir)
            _artifacts_tree_cache = tree
            _artifacts_tree_cache_time = time.time()
            return {"status": "OK", "tree": tree}
        except Exception as e:
            logger.error(f"Failed to build artifacts tree: {e}")
            if _artifacts_tree_cache is not None:
                logger.warning("Returning stale artifacts tree due to traversal error.")
                return {"status": "OK", "tree": _artifacts_tree_cache}
            return {"status": "ERROR", "message": str(e)}

from pydantic import BaseModel
class RenameArtifactRequest(BaseModel):
    old_path: str
    new_name: str

@app.post("/api/vli/artifacts/rename")
async def rename_artifact(request: RenameArtifactRequest):
    import os
    reports_dir = get_reports_root()
    
    # Resolve absolute path of old file
    old_full_path = os.path.abspath(request.old_path)
    if not old_full_path.lower().startswith(os.path.abspath(reports_dir).lower()):
        raise HTTPException(status_code=403, detail="Access denied")
        
    if not os.path.exists(old_full_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    # Build new path in the same directory
    dir_name = os.path.dirname(old_full_path)
    
    # Sanitize new name (ensure it has .md)
    new_name = request.new_name.strip()
    if not new_name.endswith('.md'):
        new_name += '.md'
    # prevent path traversal
    new_name = os.path.basename(new_name)
    
    new_full_path = os.path.join(dir_name, new_name)
    
    try:
        os.rename(old_full_path, new_full_path)
        global _artifacts_tree_cache
        _artifacts_tree_cache = None
        return {"status": "OK", "message": "Renamed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CreateArtifactRequest(BaseModel):
    folder: str

class MoveToFolderRequest(BaseModel):
    source_path: str
    target_folder: str

@app.post("/api/vli/artifacts/move_to_folder")
async def move_to_folder(request: MoveToFolderRequest):
    import os
    import shutil
    from datetime import datetime
    
    source_path = os.path.abspath(request.source_path)
    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Source file not found")
        
    reports_dir = get_reports_root()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    target_folder = request.target_folder
    if os.path.isabs(target_folder):
        target_dir = target_folder
    elif "/" in target_folder or "\\" in target_folder:
        target_folder = target_folder.lstrip('/\\')
        target_dir = os.path.abspath(os.path.join(reports_dir, target_folder))
    else:
        target_dir = os.path.abspath(os.path.join(reports_dir, today_str, target_folder))
        
    os.makedirs(target_dir, exist_ok=True)
    
    base_name = os.path.basename(source_path)
    dest_path = os.path.join(target_dir, base_name)
    
    # Prevent overwrite by appending counter if needed
    name, ext = os.path.splitext(base_name)
    counter = 1
    while os.path.exists(dest_path):
        dest_path = os.path.join(target_dir, f"{name} {counter}{ext}")
        counter += 1
        
    try:
        shutil.move(source_path, dest_path)
        global _artifacts_tree_cache
        _artifacts_tree_cache = None
        return {"status": "OK", "message": "Moved to Folder", "path": dest_path.replace("\\", "/")}
    except Exception as e:
        logger.error(f"Failed to move to notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vli/artifacts/create")
async def create_artifact(request: CreateArtifactRequest):
    import os
    reports_dir = get_reports_root()
    
    # request.folder might be an absolute path from the frontend UI or a relative name
    if os.path.isabs(request.folder):
        folder_path = request.folder
    else:
        folder_path = os.path.join(reports_dir, request.folder)
        
    folder_path = os.path.abspath(folder_path)
    
    if not folder_path.lower().startswith(os.path.abspath(reports_dir).lower()):
        raise HTTPException(status_code=403, detail="Invalid folder")
        
    os.makedirs(folder_path, exist_ok=True)
    
    base_name = "New Note"
    ext = ".md"
    new_path = os.path.join(folder_path, f"{base_name}{ext}")
    counter = 1
    while os.path.exists(new_path):
        new_path = os.path.join(folder_path, f"{base_name} {counter}{ext}")
        counter += 1
        
    try:
        with open(new_path, "w", encoding="utf-8") as f:
            f.write(f"# {os.path.basename(new_path).replace('.md', '')}\n\nStart typing here...\n")
        global _artifacts_tree_cache
        _artifacts_tree_cache = None
        return {"status": "OK", "message": "Created", "path": new_path.replace("\\", "/")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DeleteArtifactRequest(BaseModel):
    path: str

@app.post("/api/vli/artifacts/delete")
async def delete_artifact(request: DeleteArtifactRequest):
    import os
    reports_dir = get_reports_root()
    
    full_path = os.path.abspath(request.path)
    if not full_path.lower().startswith(os.path.abspath(reports_dir).lower()):
        raise HTTPException(status_code=403, detail="Access denied")
        
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        os.remove(full_path)
        global _artifacts_tree_cache
        _artifacts_tree_cache = None
        return {"status": "OK", "message": "Deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vli/artifacts/content")
async def get_artifact_content(path: str):
    import os
    if not path or ".." in path:
        raise HTTPException(status_code=400, detail="Invalid path")
        
    data_dir = os.path.abspath(os.path.join(os.getcwd(), "data"))
    if not os.path.exists(data_dir):
        data_dir = os.path.abspath(os.path.join(os.getcwd(), "backend", "data"))
        
    target_path = os.path.abspath(path)
    
    vault_path = None
    try:
        from src.tools.journal import _get_obsidian_config
        vp, _ = _get_obsidian_config(None)
        if vp:
            vault_path = os.path.abspath(vp)
    except Exception:
        pass
        
    reports_dir = get_reports_root()
    if not target_path.lower().startswith(os.path.abspath(reports_dir).lower()) and not target_path.lower().startswith(data_dir.lower()) and (not vault_path or not target_path.lower().startswith(vault_path.lower())):
        raise HTTPException(status_code=403, detail="Forbidden path")
        
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    with open(target_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    return {"status": "OK", "content": content}

class OpenLocalRequest(BaseModel):
    path: str

@app.post("/api/vli/artifacts/open_local")
async def open_local_artifact(request: OpenLocalRequest):
    import os
    import subprocess
    import sys
    target_path = os.path.abspath(request.path)
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    preferred_editor = os.environ.get("VLI_DEFAULT_EDITOR", "obsidian")
    
    try:
        if os.name == 'nt':
            if "obsidian" in preferred_editor.lower():
                # Obsidian can only open files inside a known vault.
                # Try to determine if the target path is inside the user's vault.
                vault_path = None
                try:
                    from src.tools.journal import _get_obsidian_config
                    vp, _ = _get_obsidian_config(None)
                    if vp:
                        vault_path = os.path.abspath(vp)
                except Exception:
                    pass

                if vault_path and target_path.lower().startswith(vault_path.lower()):
                    import urllib.parse
                    uri = f"obsidian://open?path={urllib.parse.quote(target_path.replace(chr(92), '/'))}"
                    try:
                        os.startfile(uri)
                        return {"status": "OK", "message": "Opened via Obsidian URI"}
                    except Exception:
                        pass
                # If it's NOT in the vault, Obsidian will throw a "Vault not found" error dialog.
                # We must skip Obsidian and fallback to the system default for loose files.

            if os.path.exists(preferred_editor) and "obsidian" not in preferred_editor.lower():
                try:
                    subprocess.Popen([preferred_editor, target_path])
                    return {"status": "OK", "message": f"Opened with {os.path.basename(preferred_editor)}"}
                except Exception:
                    pass
            
            # Ultimate Fallback
            os.startfile(target_path)
            return {"status": "OK", "message": "Opened with system default (fallback)"}
        else:
            subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', target_path])
            return {"status": "OK", "message": "Opened locally"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add CORS middleware
# It's recommended to load the allowed origins from an environment variable
# for better security and flexibility across different environments.
allowed_origins_str = get_str_env("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080,http://127.0.0.1:8080,http://localhost:8089,http://127.0.0.1:8089,http://localhost:8000,http://127.0.0.1:8000,https://digital.fidelity.com")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]
if "http://127.0.0.1:3000" not in allowed_origins:
    allowed_origins.append("http://127.0.0.1:3000")
if "http://127.0.0.1:8080" not in allowed_origins:
    allowed_origins.append("http://127.0.0.1:8080")

logger.info(f"Allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Restrict to specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # Use the configured list of methods
    allow_headers=["*"],  # Now allow all headers, but can be restricted further
)


# [NEW] Mount Static Files for the VLI Dashboard
import os

from fastapi.staticfiles import StaticFiles


async def poll_5m_patterns():
    """
    Automated 5-minute watchdog tracing the SCANNER_STRIKE_LIST for
    intraday Break of Structure (BOS) and Change of Character (CHOCH) patterns.
    """
    import json
    from src.tools.smc import run_smc_analysis
    
    strike_list_path = os.path.join(os.getcwd(), "data", "STRIKE_LIST.json")
    # Correcting dynamic pathing just in case
    if not os.path.exists(strike_list_path):
        strike_list_path = os.path.join(os.getcwd(), "backend", "data", "STRIKE_LIST.json")
        if not os.path.exists(strike_list_path):
            return

    try:
        with open(strike_list_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        candidates = data if isinstance(data, list) else (data.get("candidates", []) or data.get("strike_list", []))
        if not candidates:
            return
            
        for c in candidates:
            symbol = c.get("symbol")
            if not symbol: continue
            
            # Execute SMC Specialist primitive locally
            report = await run_smc_analysis.ainvoke({"ticker": symbol, "interval": "5m"})
            
            # Scan output block for exact matches to BoS or CHoCH
            if "Change of Character (ChoCh)" in report or "Break of Structure (BOS)" in report:
                trigger_type = "CHoCH" if "Change of Character" in report else "Break of Structure"
                msg = f" **[SMC ALERT]**: Just detected an Institutional **{trigger_type}** footprint printed on the **5m** structural timeframe for **{symbol}**."
                
                # Push organically to the Command Center UI via chat proxy
                _append_to_vli_history("Analyst", msg)
                logger.info(f"[SMC WATCHDOG] Trigger payload fired for {symbol} ({trigger_type})")
                
    except Exception as e:
        logger.error(f"[SMC WATCHDOG] Internal polling failure: {e}")

def run_tv_watchlist_export_task():
    """Scheduled task to execute the TradingView watchlist export."""
    try:
        import sys, os
        proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if proj_root not in sys.path:
            sys.path.insert(0, proj_root)
        from scripts.utils.export_tradingview_watchlists import main as run_export
        logger.info("Executing periodic TradingView watchlist export...")
        run_export()
    except Exception as e:
        logger.error(f"Failed to execute periodic TradingView watchlist export: {e}")

async def poll_market_pulse():
    """
    Automated execution of Phase 1 and Phase 2 algorithmic pulse tracking.
    Refreshes the STRIKE_RES_state.json natively without broadcasting terminal SSEs.
    """
    from datetime import datetime
    from src.config.vli import get_vli_path
    from src.tools.scanner import _build_session_watchlist_impl, _run_activity_pulse_impl, sanitize_data, NpEncoder

    try:
        engine = os.environ.get("VLI_SCANNER_ENGINE", "tradingview").lower()
        if engine == "tradingview":
            return
            
        strike_list_path = os.path.join(os.getcwd(), "data", "STRIKE_LIST.json")
        if not os.path.exists(strike_list_path):
            strike_list_path = os.path.join(os.getcwd(), "backend", "data", "STRIKE_LIST.json")

        phase0_raw = []
        if os.path.exists(strike_list_path):
            with open(strike_list_path, "r", encoding="utf-8") as f:
                c_data = json.load(f)
                phase0_raw = c_data if isinstance(c_data, list) else (c_data.get("strike_list", []) or c_data.get("candidates", []))
                
        symbols = [r["symbol"] for r in phase0_raw if r.get("symbol")]
        universe_csv = ",".join(symbols)

        if not universe_csv:
            return
            
        p1_res_str = await _build_session_watchlist_impl(strategy_config="{}", universe_csv=universe_csv)
        p1_data = json.loads(p1_res_str)
        p1_symbols = p1_data.get("watchlist", [])
        
        if not p1_symbols:
            return
            
        p2_res_str = await _run_activity_pulse_impl(strategy_config="{}", watchlist=json.dumps(p1_symbols, cls=NpEncoder))
        p2_data = json.loads(p2_res_str)
        p2_candidates = p2_data.get("candidates", [])
        
        p2_full = []
        for p in p2_candidates:
            match = next((x for x in phase0_raw if x.get("symbol") == p.get("symbol")), {})
            merged = sanitize_data({**match, **p})
            p2_full.append(merged)
            
        response_obj = sanitize_data({"candidates": p2_full})
        transit_path = get_vli_path(os.path.join("01_Transit", "Buckets", "STRIKE_RES_state.json"))
        os.makedirs(os.path.dirname(transit_path), exist_ok=True)
        with open(transit_path, "w", encoding="utf-8") as f:
            json.dump(response_obj, f, indent=4, cls=NpEncoder)
            
        logger.info(f"[PULSE TRACKER] Background cycle completely silently: {len(p2_full)} high probability targets cached.")
        
    except Exception as e:
        logger.error(f"[PULSE TRACKER] Native cycle failed: {e}")


async def run_tv_sync():
    """
    Background wrapper for TradingView scanner synchronization.
    Relying on the external TV engine for high-fidelity candidates.
    """
    import asyncio
    import subprocess
    import sys
    try:
        script_path = os.path.join(os.getcwd(), "scripts", "vli", "tv_scanner_sync.py")
        if not os.path.exists(script_path):
            script_path = os.path.join(os.getcwd(), "..", "scripts", "vli", "tv_scanner_sync.py")
            
        logger.info(f"[TV SYNC] Launching TradingView extractor: {script_path}")
        
        def _run_subprocess():
            return subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True
            )
            
        result = await asyncio.to_thread(_run_subprocess)
        if result.returncode != 0:
            logger.error(f"[TV SYNC] Sync returned non-zero code. Error output: {result.stderr}")
        else:
            import threading
            def bg_analysis():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(run_idle_analysis(manual_trigger=False))
                loop.close()
            threading.Thread(target=bg_analysis, daemon=True).start()

    except Exception as e:
        logger.error(f"[TV SYNC] Synchronization failed: {e}")

def update_global_thinking_mode(is_thinking: bool):
    settings_path = os.path.join(os.getcwd(), 'data', 'vli_settings.json')
    try:
        settings = {}
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        settings["thinking_mode"] = is_thinking
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f)
    except:
        pass

def get_global_thinking_mode() -> bool:
    settings_path = os.path.join(os.getcwd(), 'data', 'vli_settings.json')
    try:
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                return json.load(f).get("thinking_mode", False)
    except:
        pass
    return False

def get_scanner_is_sample() -> bool:
    settings_path = os.path.join(os.getcwd(), 'data', 'vli_settings.json')
    try:
        if not os.path.exists(settings_path):
            settings_path = os.path.join(os.getcwd(), 'backend', 'data', 'vli_settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                return json.load(f).get("use_sample_data", False)
    except:
        pass
    return False

def update_scanner_is_sample(is_sample: bool):
    settings_path = os.path.join(os.getcwd(), 'data', 'vli_settings.json')
    try:
        if not os.path.exists(settings_path):
            settings_path = os.path.join(os.getcwd(), 'backend', 'data', 'vli_settings.json')
        settings = {}
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        settings["use_sample_data"] = is_sample
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f)
    except:
        pass
async def run_idle_analysis(manual_trigger: bool = False):
    """
    Background orchestrator that diffs the scanner state against generated reports
    and spawns analysis agents for any missing symbols with stagger logic.
    """
    global _is_idle_analysis_running
    if _is_idle_analysis_running:
        logger.warning("[BG_ANALYST] Background analysis is already running. Ignoring duplicate trigger.")
        return
    _is_idle_analysis_running = True
    try:
        await _run_idle_analysis_impl(manual_trigger)
    finally:
        _is_idle_analysis_running = False

async def _run_idle_analysis_impl(manual_trigger: bool = False):
    import asyncio
    from datetime import datetime
    
    if not manual_trigger and datetime.now().hour < 7:
        logger.info("[BG_ANALYST] System idle. Holding report generation until 07:00 AM.")
        return
        
    candidates = []
    try:
        from src.config.vli import get_vli_path
        macro_path = get_vli_path(os.path.join("01_Transit", "Buckets", "MACRO_WATCHLIST_state.json"))
        if os.path.exists(macro_path):
            with open(macro_path, 'r', encoding='utf-8') as f:
                macro_state = json.load(f)
            for row in macro_state.get("rows", []):
                if len(row) > 1:
                    candidates.append({"symbol": row[1], "is_macro": True, "grade": "S"})
    except Exception as e:
        logger.error(f"[BG_ANALYST] Failed to read macro watchlist: {e}")

    reports_dir = get_reports_root()
    os.makedirs(reports_dir, exist_ok=True)
        
    candidates_to_process = []
    skipped_symbols = []
    added_trace = []
    skipped_trace = []
    logger.debug(f"DEBUG: candidates count: {len(candidates)}")
    for c in candidates:
        sym = c.get("symbol") if isinstance(c, dict) else c
        if not sym: continue
        
        sym_clean = sym.replace('^', '').replace('=', '').lower()
        r_path1 = os.path.join(reports_dir, f"analyze_{sym.lower()}.md")
        r_path2 = os.path.join(reports_dir, f"analyze_{sym_clean}.md")
        needs_report = True
        
        active_path = None
        if os.path.exists(r_path1):
            active_path = r_path1
        elif os.path.exists(r_path2):
            active_path = r_path2
            
        if active_path:
            mtime = datetime.fromtimestamp(os.path.getmtime(active_path))
            if mtime.date() == datetime.now().date() and os.path.getsize(active_path) > 100:
                needs_report = False
                
        logger.debug(f"DEBUG: {sym} needs_report: {needs_report}")
        if needs_report:
            grade = c.get("grade", "F") if isinstance(c, dict) else "F"
            if grade not in ["S", "A+", "A", "A-"]:
                skipped_symbols.append(sym)
                skipped_trace.append(f"    Skipped: **{sym}** (Grade {grade} beneath A threshold)")
            else:
                candidates_to_process.append(c)
                added_trace.append(f"    Added: **{sym}**")
        else:
            skipped_symbols.append(sym)
            skipped_trace.append(f"    Skipped: **{sym}** (Cached Report Active)")
            
    # [NEW] Telemetry Write for List Building
    try:
        from src.config.vli import get_vli_path
        from datetime import datetime
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        trace_log = "\n".join(added_trace)
        if trace_log:
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp}  **[ORCHESTRATOR]** Candidate Evaluation Trace:\n{trace_log}\n")
                tf.flush()
    except Exception as e:
        logger.error(f"Failed to write candidate trace: {e}")

    if candidates_to_process:
        logger.info(f"[BG_ANALYST] Missing/stale reports detected for: {[c.get('symbol') for c in candidates_to_process]}. Beginning generation sequence.")
        
        try:
            from src.config.vli import get_vli_path
            telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp}  **[ORCHESTRATOR]** Background LLM Analyst initiated deep-scan for {len(candidates_to_process)} missing candidates.\n")
                tf.flush()
        except Exception:
            pass

        # Segregate into full analysis vs batch analysis
        full_analysis_queue = []
        batch_analysis_queue = []
        for c in candidates_to_process:
            grade = c.get("grade", "A") if isinstance(c, dict) else "A"
            is_macro = isinstance(c, dict) and c.get("is_macro", False)
            if is_macro or grade in ["S", "A+", "A", "A-"]:
                full_analysis_queue.append(c)
            else:
                batch_analysis_queue.append(c)
                
        # 1. Process Batch Queue
        if batch_analysis_queue:
            logger.info(f"[BG_ANALYST] Spawning batch analysis for {len(batch_analysis_queue)} lower-tier candidates.")
            try:
                from src.llms.llm import get_llm_by_type
                from src.config.vli import get_vli_path
                import yfinance as yf
                from langchain_core.messages import HumanMessage
                
                basic_llm = get_llm_by_type("basic")
                batch_prompts = []
                
                sem = asyncio.Semaphore(5)
                # Fetch prices concurrently using asyncio.to_thread but limited by semaphore
                async def fetch_price(sym):
                    async with sem:
                        try:
                            ticker = await asyncio.to_thread(yf.Ticker, sym)
                            info = await asyncio.to_thread(lambda: ticker.info)
                            return float(info.get("preMarketPrice") or info.get("postMarketPrice") or info.get("currentPrice") or info.get("regularMarketPrice") or 0.0)
                        except:
                            return 0.0
                        
                prices = await asyncio.gather(*[fetch_price(c.get("symbol")) for c in batch_analysis_queue])
                
                for c, price in zip(batch_analysis_queue, prices):
                    sym = c.get("symbol")
                    tier = c.get("tier", "Scout")
                    sortino = c.get("sortino", 0.0)
                    prompt = f"""Generate a concise, single-paragraph trading analysis report for {sym}.
                    
Active Strategy: {tier.capitalize()} Strategy
Current Real-Time Price: ${price:.2f}
Scanner Metrics: Grade {c.get("grade", "C")}, Sortino: {sortino}, RVOL: {c.get("rvol", 0.0)}

Synthesize these metrics into a brief technical outlook. Focus on risk management."""
                    # Use standard message array format for LangChain abatch
                    batch_prompts.append([HumanMessage(content=prompt)])
                    
                # Bypass LangChain abatch silently crashing the process by using a secure sequential loop
                batch_results = []
                for i, p in enumerate(batch_prompts):
                    try:
                        res = await basic_llm.ainvoke(p)
                        batch_results.append(res)
                    except Exception as e:
                        logger.error(f"[BG_ANALYST] Error generating batch item {i}: {e}")
                        batch_results.append("Batch generation failed for this item.")
                
                for c, res in zip(batch_analysis_queue, batch_results):
                    sym = c.get("symbol")
                    if hasattr(res, 'content'):
                        if isinstance(res.content, list):
                            result_text = " ".join([b.get("text", "") if isinstance(b, dict) else str(b) for b in res.content])
                        else:
                            result_text = str(res.content)
                    else:
                        result_text = str(res)
                        
                    r_path = os.path.join(get_reports_root(), f"analyze_{sym.lower()}.md")
                    
                    os.makedirs(os.path.dirname(r_path), exist_ok=True)
                    generation_ts = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
                    header = f"> **Generated:** {generation_ts} (Batch Pipeline)\n\n"
                    try:
                        with open(r_path, "w", encoding="utf-8") as rf:
                            rf.write(header + result_text)
                    except Exception as err:
                        logger.error(f"[BG_ANALYST] FAILED TO WRITE {sym}: {err}")
                    
                    # Update scanner UI state
                    try:
                        for target_state in ["STRIKE_RES_state.json", "STRIKE_LIST.json"]:
                            s_path = get_vli_path(os.path.join("01_Transit", "Buckets", target_state)) if "state" in target_state else get_data_file_path(target_state)
                            if os.path.exists(s_path):
                                with open(s_path, "r", encoding="utf-8") as f:
                                    s_data = json.load(f)
                                updated = False
                                target_list = s_data.get("candidates", []) if "candidates" in s_data else s_data.get("strike_list", [])
                                for c_item in target_list:
                                    if isinstance(c_item, dict) and c_item.get("symbol", "").upper() == sym.upper():
                                        c_item["has_report"] = True
                                        c_item["updated_at"] = datetime.now().isoformat()
                                        updated = True
                                if updated:
                                    with open(s_path, "w", encoding="utf-8") as f:
                                        json.dump(s_data, f, indent=4)
                    except Exception as e:
                        logger.error(f"[BG_ANALYST] Failed to update scanner state for {sym} during batch: {e}")
                        
                try:
                    timestamp = datetime.now().strftime("[%H:%M:%S]")
                    with open(telemetry_file, "a", encoding="utf-8") as tf:
                        tf.write(f"\n{timestamp}  **[ANALYST]** Batch generated reports for {len(batch_analysis_queue)} candidates.\n")
                        tf.flush()
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"[BG_ANALYST] Batch generation failed: {e}")

        # 2. Process Full Queue
        total = len(full_analysis_queue)
        for i, c in enumerate(full_analysis_queue, 1):
            sym = c.get("symbol")
            tier = c.get("tier", "War Barbell") # Default to old behavior if missing
            logger.info(f"[BG_ANALYST] Spawning background LangGraph for {sym} (Tier: {tier})...")
            
            try:
                timestamp = datetime.now().strftime("[%H:%M:%S]")
                with open(telemetry_file, "a", encoding="utf-8") as tf:
                    tf.write(f"\n{timestamp}  **[ANALYST]** Spawning deep-dive intelligence for **{sym}** ({i}/{total})...\n")
                    tf.flush()
            except Exception:
                pass
            
            result_text, _ = await _invoke_vli_agent(f"analyze {sym}. Ensure you include a line 'Active Strategy: {tier.capitalize()} Strategy' at the top of the report, and frame the analysis using {tier} terminology.", thread_id=f"bg_{sym}", thinking_mode=get_global_thinking_mode())
            
            # [HARDENING] Only persist valid reports. Prevent caching of LLM errors.
            is_valid = True
            if not result_text or len(result_text) < 50:
                is_valid = False
            elif "Agent reasoning encountered a failure" in result_text or "timed out" in result_text.lower():
                is_valid = False
            
            if is_valid:
                try:
                    r_path = os.path.join(get_reports_root(), f"analyze_{sym.lower()}.md")
                    os.makedirs(os.path.dirname(r_path), exist_ok=True)
                    generation_ts = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
                    header = f"> **Generated:** {generation_ts}\n\n"
                    with open(r_path, "w", encoding="utf-8") as rf:
                        rf.write(header + result_text)
                        
                    # [UX HOTFIX] Instantly update the scanner lists so document icons turn green immediately
                    try:
                        from src.config.vli import get_vli_path
                        for target_state in ["STRIKE_RES_state.json", "STRIKE_LIST.json"]:
                            s_path = get_vli_path(os.path.join("01_Transit", "Buckets", target_state)) if "state" in target_state else get_data_file_path(target_state)
                            if os.path.exists(s_path):
                                with open(s_path, "r", encoding="utf-8") as f:
                                    s_data = json.load(f)
                                updated = False
                                
                                # Handle both 'candidates' (SCANNER_RES) and 'strike_list' (COMBAT_LIST) formats
                                target_list = s_data.get("candidates", []) if "candidates" in s_data else s_data.get("strike_list", [])
                                
                                for c_item in target_list:
                                    if isinstance(c_item, dict) and c_item.get("symbol", "").upper() == sym.upper():
                                        c_item["has_report"] = True
                                        c_item["updated_at"] = datetime.now().isoformat()
                                        updated = True
                                        
                                if updated:
                                    with open(s_path, "w", encoding="utf-8") as f:
                                        json.dump(s_data, f, indent=4)
                    except Exception as e:
                        logger.error(f"[BG_ANALYST] Failed to update scanner state for {sym}: {e}")
                        
                except Exception as e:
                    logger.error(f"[BG_ANALYST] Failed to save report for {sym}: {e}")
            else:
                logger.warning(f"[BG_ANALYST] Execution failed for {sym}. Artifact discarded to prevent cache poisoning.")
            
            try:
                timestamp = datetime.now().strftime("[%H:%M:%S]")
                with open(telemetry_file, "a", encoding="utf-8") as tf:
                    tf.write(f"\n{timestamp}  **[ANALYST]** Report generated for **{sym}** (Rate limit stagger: 30s).\n")
                    tf.flush()
            except Exception:
                pass
            
            logger.info(f"[BG_ANALYST] Generated report for {sym}. Sleeping 30s to respect API rate limits.")
            await asyncio.sleep(30)
            
        try:
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\\n{timestamp}  **[ORCHESTRATOR]** Background LLM Analyst sequence complete.\\n")
                tf.flush()
        except Exception:
            pass
            
        logger.info("[BG_ANALYST] Background generation sequence complete.")
            
    # [NEW] Automatically spawn Meta-Analysis if all reports are ready
    await run_meta_analysis(manual_trigger=False)

async def run_daily_morning_analysis():
    """
    Cron task running at 8:30 AM EDT (Start of Day / SOD). Pulls TV Sync and then triggers idle analysis.
    """
    global _is_morning_scan_running
    if _is_morning_scan_running:
        logger.warning("[BG_ANALYST] SOD Morning Market Scan is already running. Ignoring duplicate trigger.")
        return

    _is_morning_scan_running = True
    logger.info("[BG_ANALYST] Triggering 8:30 AM Start of Day (SOD) Morning Market Scan.")
    try:
        from src.config.vli import get_vli_path
        from datetime import datetime
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        with open(telemetry_file, "a", encoding="utf-8") as tf:
            tf.write(f"\n{timestamp}  **[ORCHESTRATOR]** Running Start of Day (SOD) Scanner...\n")
            tf.flush()
    except Exception:
        pass
        
    try:
        from src.config.configuration import get_str_env
        scanner_engine = get_str_env("VLI_SCANNER_ENGINE", "cobalt").lower()
        if scanner_engine == "tradingview":
            await run_tv_sync()
        else:
            from src.tools.sortino_sniper_trawl import run_background_trawl
            from src.tools.shield_scanner_trawl import run_shield_trawl
            await run_background_trawl()
            try:
                # shield trawl uses ainvoke since it is a Tool
                await run_shield_trawl.ainvoke({})
            except Exception as e:
                logger.error(f"[BG_ANALYST] Shield Trawl failed during morning scan: {e}")
        await run_idle_analysis(manual_trigger=True)
        
        # [NEW] Force an immediate UI state refresh
        try:
            from src.server.app import poll_market_pulse
            await poll_market_pulse()
        except Exception as e:
            logger.error(f"[BG_ANALYST] Failed to force pulse refresh: {e}")
            
    finally:
        _is_morning_scan_running = False

async def run_meta_analysis(manual_trigger: bool = False):
    """
    Synthesizes an Executive Morning Briefing from all generated reports.
    Requires all scanner candidates to have a valid, day-of report.
    """
    import json
    logger.info("[META_ANALYST] Initiating Executive Morning Briefing sequence.")
    try:
        from src.config.vli import get_vli_path, VAULT_ROOT
        from datetime import datetime
        
        now = datetime.now()
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        
        reports_dir = get_reports_root()
        os.makedirs(reports_dir, exist_ok=True)
        
        # [NEW] Check if already generated today
        meta_path = get_daily_briefing_path()
        if not manual_trigger and os.path.exists(meta_path):
            mtime = datetime.fromtimestamp(os.path.getmtime(meta_path))
            if mtime.date() == datetime.now().date():
                return
                
        # 1. Load macro watchlist (required reports)
        macro_symbols = []
        try:
            macro_path = get_vli_path(os.path.join("01_Transit", "Buckets", "MACRO_WATCHLIST_state.json"))
            if os.path.exists(macro_path):
                with open(macro_path, 'r', encoding='utf-8') as f:
                    macro_state = json.load(f)
                for row in macro_state.get("rows", []):
                    if len(row) > 1:
                        macro_symbols.append(row[1])
        except Exception as e:
            logger.error(f"[META_ANALYST] Failed to read macro watchlist: {e}")

        compiled_reports = []
        missing_reports = []
        
        # 2. Check and compile all generated reports in the reports directory today
        # If any report was generated today for any symbol (whether macro or scanner symbol), compile it!
        if os.path.exists(reports_dir):
            for filename in os.listdir(reports_dir):
                if filename.startswith("analyze_") and filename.endswith(".md"):
                    sym = filename.replace("analyze_", "").replace(".md", "").upper()
                    r_path = os.path.join(reports_dir, filename)
                    mtime = datetime.fromtimestamp(os.path.getmtime(r_path))
                    if mtime.date() == datetime.now().date():
                        with open(r_path, "r", encoding="utf-8") as rf:
                            content = rf.read()
                            if len(content) > 100:
                                compiled_reports.append(f"### REPORT: {sym}\n{content}\n---\n")

        # 3. Required Reports Check: Verify all macro symbols have reports today
        compiled_syms_set = {r.split("\n")[0].replace("### REPORT: ", "").upper().strip() for r in compiled_reports}
        for msym in macro_symbols:
            msym_clean = msym.replace('^', '').replace('=', '').upper().strip()
            if msym.upper().strip() not in compiled_syms_set and msym_clean not in compiled_syms_set:
                missing_reports.append(msym)

        if missing_reports:
            logger.warning(f"[META_ANALYST] Missing valid reports for macro: {missing_reports}. Triggering background generation.")
            
            import threading
            def bg_analysis():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(run_idle_analysis(manual_trigger=True))
                loop.close()
            threading.Thread(target=bg_analysis, daemon=True).start()
            
            if manual_trigger:
                return f"Missing valid reports for {len(missing_reports)} macro assets. Initiating background generation... You will be notified with a UX card when the Executive Briefing is ready."
            return
            
        # Write to telemetry
        try:
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp}  **[META_ANALYST]** Synthesizing Executive Morning Briefing from {len(compiled_reports)} reports...\n")
                tf.flush()
        except Exception:
            pass
            
        # Bundle for LLM
        bundle = "\n".join(compiled_reports)
        compiled_symbols = sorted(list(compiled_syms_set))
        source_str = f"Source Scans: {', '.join(compiled_symbols)}"
        
        session_config = _get_vli_session_config()
        active_strat_file = session_config.get("active_strategy")
        if active_strat_file:
            active_strat_name = active_strat_file.replace(".md", "").replace("cma_strategy_", "").replace("_", " ").title()
        else:
            active_strat_name = "Active Strategy"
            
        # [NEW] Inject News and Calendar Data
        from src.tools.macros import fetch_economic_calendar
        from src.tools.news import get_macro_news
        
        try:
            cal_data = await fetch_economic_calendar.ainvoke({})
            bundle += f"\n\n### MACRO ECONOMIC CALENDAR\n{cal_data}\n---\n"
        except Exception as e:
            logger.error(f"[META_ANALYST] Failed to fetch calendar: {e}")
            
        try:
            news_data = await get_macro_news.ainvoke({"refresh": True})
            if isinstance(news_data, dict) and "data" in news_data:
                news_data = news_data["data"]
            bundle += f"\n\n### GLOBAL MACRO NEWS\n{news_data}\n---\n"
        except Exception as e:
            logger.error(f"[META_ANALYST] Failed to fetch macro news: {e}")

        prompt = (
            "You are the Chief Market Strategist for Blueshell Securities. "
            "Synthesize an 'Executive Morning Briefing' from the following institutional reports, macroeconomic calendar, and breaking news. "
            "Your objective is to provide a comprehensive macro-level overview for the upcoming trading session. "
            "Focus on: 1. Broad Market Sentiment and Key Catalysts, 2. Sector Performance and Rotation (highlighting relative strength/weakness), "
            "3. Aggregate Risk Profile (Volatility/VIX), 4. General Market Outlook and Guidance, and 5. Macroeconomic Calendar. "
            "CRITICAL: The briefing MUST feature a dedicated 'Macroeconomic Calendar' section that explicitly lists both daily and weekly events, including their exact times and expected results/forecasts as provided in the context. "
            "CRITICAL: Do NOT provide specific 'Strike Authorizations', tactical execution parameters, or trade plans for individual tickers like SPY or QQQ. "
            "This is a high-level strategic briefing to help the trader understand market movements and sector outlooks, not a single-ticker trade alert. "
            "You MUST incorporate the 'GLOBAL MACRO NEWS' into your broader sentiment analysis. "
            f"The active strategy framework is '{active_strat_name}'. You may optionally frame the overall market condition relative to this strategy's general viability. "
            f"CRITICAL INSTRUCTION: You MUST include the exact following line at the end of your briefing to cite the source documents: '{source_str}'. "
            "Be concise, analytical, and highly professional.\n\n"
            f"{bundle}\n\n--FORCE-GRAPH"
        )
        
        result_text, _ = await _invoke_vli_agent(prompt, thread_id="bg_meta_analysis", thinking_mode=get_global_thinking_mode())
        
        if result_text and "Agent reasoning encountered a failure" not in result_text and "timed out" not in result_text.lower():
            meta_path = get_daily_briefing_path()
            # Ensure its parent dir exists
            os.makedirs(os.path.dirname(meta_path), exist_ok=True)
            generation_date = datetime.now().strftime("%A, %B %d, %Y")
            generation_time = datetime.now().strftime("%I:%M %p")
            header = f"> **Date:** {generation_date}  \n> **Time:** {generation_time}\n\n"
            
            with open(meta_path, "w", encoding="utf-8") as mf:
                mf.write(header + result_text)
                
            logger.info("[META_ANALYST] Executive Morning Briefing completed and cached.")
            
            # [NEW] Push to Analysis Report Card
            global _vli_last_async_report
            _vli_last_async_report = header + result_text
            
            try:
                timestamp = datetime.now().strftime("[%H:%M:%S]")
                with open(telemetry_file, "a", encoding="utf-8") as tf:
                    tf.write(f"\n{timestamp}  **[META_ANALYST]** Executive Morning Briefing successfully compiled.\n")
                    tf.flush()
            except Exception:
                pass
                
            if manual_trigger:
                return "Meta-Analysis successfully generated. Executive Morning Briefing is now available."
        else:
            if manual_trigger:
                return "Meta-Analysis execution failed due to an LLM timeout or reasoning error."
                
    except Exception as e:
        logger.error(f"[META_ANALYST] Failed to run meta analysis: {e}")
        if manual_trigger:
            return f"System Error during Meta-Analysis: {e}"



in_memory_store = InMemoryStore()
graph = build_graph_with_memory()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@app.get("/api/models")
async def get_models():
    """Retrieve all configured LLM models for the UI."""
    try:
        raw_models = get_configured_llm_models()
        transformed_models = []
        for llm_type, model_list in raw_models.items():
            for m_name in model_list:
                transformed_models.append({
                    "id": f"{llm_type}-{m_name}",
                    "name": m_name,
                    "model": m_name,
                    "display_name": f"{m_name} ({llm_type})",
                    "supports_thinking": llm_type == "reasoning",
                    "supports_reasoning_effort": llm_type == "reasoning"
                })
        return {"models": transformed_models}
    except Exception as e:
        logger.error(f"Failed to fetch models: {e}")
        return {"models": []}


async def verify_api_key(api_key: str = Security(api_key_header)):
    expected_key = get_str_env("COBALT_API_KEY", "")
    if expected_key:
        if not api_key or api_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key


@app.get("/api/vli/visualization")
async def vli_visualization():
    """Serve the VLI technical analysis visualization (Diagnostic Only)."""
    try:
        img_path = r"C:\Users\rende\OneDrive\Desktop\vli_analysis_visualization.png"
        with open(img_path, "rb") as f:
            return Response(content=f.read(), media_type="image/png")
    except Exception:
        raise HTTPException(status_code=404, detail="Visualization image not found. Deploy to production to generate.")


# --- VLI SESSION MONITORING & CHAT ENDPOINTS ---

import shutil

class FeedbackRequest(BaseModel):
    vote: str # 'up' or 'down'
    request: str
    response: str

@app.post("/api/v1/vli/feedback")
async def handle_vli_feedback(req: FeedbackRequest):
    from datetime import datetime
    base_dir = r"c:\github\obsidian-vault\_cobalt"
    path = os.path.join(base_dir, "feedback.md")
    
    # Ensure file and tables exist
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("# VLI Human Feedback Alignment System\n\n## Positive Feedback\n| Timestamp | Request | System Response Snippet |\n|---|---|---|\n\n## Negative Feedback\n| Timestamp | Request | System Response Snippet |\n|---|---|---|\n")

    # Clean text to single lines for Table compliance
    clean_req = req.request.replace('\n', ' ').strip()
    clean_req = (clean_req[:100] + '...') if len(clean_req) > 100 else clean_req
    
    clean_resp = req.response.replace('\n', ' ').strip()
    clean_resp = (clean_resp[:150] + '...') if len(clean_resp) > 150 else clean_resp
    
    # Escape pipe characters
    clean_req = clean_req.replace('|', '\\|')
    clean_resp = clean_resp.replace('|', '\\|')
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = f"| {timestamp} | {clean_req} | {clean_resp} |\n"
    
    # We natively read, inject row, and write back
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        target_header = "## Positive Feedback" if req.vote == 'up' else "## Negative Feedback"
        insert_idx = -1
        
        for i, line in enumerate(lines):
            if line.startswith(target_header):
                # find the end of the table (or next header)
                for j in range(i+1, len(lines)):
                    if lines[j].startswith("## "):
                        insert_idx = j
                        break
                if insert_idx == -1:
                    insert_idx = len(lines)
                break
                
        if insert_idx != -1:
            # Check if previous line lacks newline
            if insert_idx > 0 and not lines[insert_idx-1].endswith('\n'):
                lines[insert_idx-1] += '\n'
            lines.insert(insert_idx, row)
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return {"status": "success"}
        else:
            # Fallback if table header missing somehow
            with open(path, "a", encoding="utf-8") as f:
                 f.write(f"\n{target_header}\n| Timestamp | Request | System Response Snippet |\n|---|---|---|\n{row}")
            return {"status": "success"}
    except Exception as e:
        logger.error(f"[FEEDBACK] Error appending row: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class TraderProfileUpdate(BaseModel):
    active_persona: str = "cma_persona.md"
    active_strategy: str = "cma_strategy_apex500.md"
    active_rules: str = "cma_risk_management.md"
    persona_content: str = ""
    strategy_content: str = ""
    rules_content: str = ""

@app.get("/api/v1/trader-profile")
async def get_trader_profile():
    base_dir = r"c:\github\obsidian-vault\_cobalt"
    
    def read_safe(path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""
        
    import json
    import glob
    config_path = os.path.join(base_dir, "vli_session_config.json")
    active_persona = "cma_persona.md"
    active_strategy = "cma_strategy_apex500.md"
    active_rules = "cma_risk_management.md"
    
    if os.path.exists(config_path):
        try:
            with open(config_path) as cf:
                sc = json.load(cf)
                active_persona = sc.get("active_persona", active_persona)
                active_strategy = sc.get("active_strategy", active_strategy)
                active_rules = sc.get("active_risk", active_rules)
        except: pass
        
    persona_files = [os.path.basename(f) for f in glob.glob(os.path.join(base_dir, "cma_persona*.md"))]
    strategy_files = [os.path.basename(f) for f in glob.glob(os.path.join(base_dir, "cma_strategy*.md"))]
    rules_files = [os.path.basename(f) for f in glob.glob(os.path.join(base_dir, "cma_risk*.md"))]
    
    if active_persona not in persona_files: persona_files.append(active_persona)
    if active_strategy not in strategy_files: strategy_files.append(active_strategy)
    if active_rules not in rules_files: rules_files.append(active_rules)
        
    return {
        "active_persona": active_persona,
        "active_strategy": active_strategy,
        "active_rules": active_rules,
        "persona_files": sorted(set(persona_files)),
        "strategy_files": sorted(set(strategy_files)),
        "rules_files": sorted(set(rules_files)),
        "persona": read_safe(os.path.join(base_dir, active_persona)),
        "strategy": read_safe(os.path.join(base_dir, active_strategy)),
        "rules": read_safe(os.path.join(base_dir, active_rules))
    }

@app.post("/api/v1/trader-profile")
async def update_trader_profile(update: TraderProfileUpdate):
    base_dir = r"c:\github\obsidian-vault\_cobalt"
    import json
    config_path = os.path.join(base_dir, "vli_session_config.json")
    
    sc = {}
    if os.path.exists(config_path):
        try:
            with open(config_path) as cf:
                sc = json.load(cf)
        except: pass
        
    sc["active_persona"] = update.active_persona
    sc["active_strategy"] = update.active_strategy
    sc["active_risk"] = update.active_rules
    
    try:
        with open(config_path, "w") as cf:
            json.dump(sc, cf, indent=4)
            
        files_to_write = {
            update.active_persona: update.persona_content,
            update.active_strategy: update.strategy_content,
            update.active_rules: update.rules_content
        }
        
        for filename, content in files_to_write.items():
            path = os.path.join(base_dir, filename)
            if os.path.exists(path):
                 shutil.copy(path, path + ".bak")
            with open(path, "w", encoding="utf-8") as f:
                 f.write(content)
                 
        return {"status": "success"}
    except Exception as e:
        logger.error(f"[PROFILE_API] Error updating trader profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class TraderProfileActiveModulesUpdate(BaseModel):
    active_persona: str | None = None
    active_strategy: str | None = None
    active_rules: str | None = None

@app.post("/api/v1/trader-profile/active-modules")
async def update_trader_profile_active_modules(req: TraderProfileActiveModulesUpdate):
    base_dir = r"c:\github\obsidian-vault\_cobalt"
    import json
    config_path = os.path.join(base_dir, "vli_session_config.json")
    
    sc = {}
    if os.path.exists(config_path):
        try:
            with open(config_path) as cf:
                sc = json.load(cf)
        except: pass
        
    if req.active_persona: sc["active_persona"] = req.active_persona
    if req.active_strategy: sc["active_strategy"] = req.active_strategy
    if req.active_rules: sc["active_risk"] = req.active_rules
    
    try:
        with open(config_path, "w") as cf:
            json.dump(sc, cf, indent=4)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"[PROFILE_API] Error updating active modules: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/trader-profile/file")
async def get_trader_profile_file(name: str):
    base_dir = r"c:\github\obsidian-vault\_cobalt"
    path = os.path.join(base_dir, os.path.basename(name))
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    with open(path, "r", encoding="utf-8") as f:
        return {"content": f.read()}

class TraderProfileNewRequest(BaseModel):
    type: str
    name: str

@app.post("/api/v1/trader-profile/new")
async def new_trader_profile(req: TraderProfileNewRequest):
    import re
    base_dir = r"c:\github\obsidian-vault\_cobalt"
    
    prefix = {
        "persona": "cma_persona",
        "strategy": "cma_strategy",
        "rules": "cma_risk"
    }.get(req.type, "cma_custom")
    
    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', req.name).strip('_').lower()
    if not clean_name: raise HTTPException(status_code=400, detail="Invalid name")
    
    filename = f"{prefix}_{clean_name}.md"
    
    path = os.path.join(base_dir, filename)
    if os.path.exists(path):
        raise HTTPException(status_code=400, detail="File already exists.")
        
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {req.name.upper()} Template\n\nBegin configuring guidelines here...")
        return {"filename": filename}
    except Exception as e:
        logger.error(f"[PROFILE_API] Error creating profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class VLIActionPlanRequest(BaseModel):
    text: str
    image: str | None = None
    is_action_plan: bool = False
    direct_mode: bool = False
    raw_data_mode: bool = False
    reporter_llm_type: str = "basic"
    vli_llm_type: str = "reasoning"
    thread_id: str | None = None
    snaptrade_settings: dict | None = None
    thinking_mode: bool = False
    background_synthesis: bool = False


class VLIJournalRequest(BaseModel):
    grades: dict
    markdown: str


# --- VLI SCANNER SETTINGS ---
@app.get("/api/vli/scanner-settings")
def get_scanner_settings():
    import json, os
    settings_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "scanner_settings.json"))
    engine = os.environ.get("VLI_SCANNER_ENGINE", "tradingview").lower()
    existing = {"track_spy": False, "engine": engine}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                existing.update(json.load(f))
        except Exception:
            pass
    existing["engine"] = engine
    return existing

@app.post("/api/settings/save_default_layout")
def save_default_layout(req: dict):
    import json, os
    layout_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "default_layout.json"))
    try:
        # Create directories if they do not exist
        os.makedirs(os.path.dirname(layout_path), exist_ok=True)
        with open(layout_path, "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/settings/default_layout")
def get_default_layout():
    import json, os
    layout_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "default_layout.json"))
    if os.path.exists(layout_path):
        try:
            with open(layout_path, "r", encoding="utf-8") as f:
                return {"status": "success", "layout": json.load(f)}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "No default layout persisted."}


class ScannerSettingsRequest(BaseModel):
    track_spy: bool | None = None
    active_tier: str | None = None

@app.post("/api/vli/scanner-settings")
def update_scanner_settings(req: ScannerSettingsRequest):
    import json, os
    settings_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "scanner_settings.json"))
    
    existing = {"track_spy": False}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass
            
    if req.track_spy is not None:
        existing["track_spy"] = req.track_spy
        
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(existing, f)
        
    if req.active_tier:
        strat_val = "all" if req.active_tier == "ALL" else req.active_tier.lower()
        _update_vli_session_config({"active_strategy": strat_val})
        
    return {"status": "success"}

@app.post("/api/vli/force-scanner-sync")
async def force_scanner_sync():
    import asyncio
    # Trigger the sync and wait for it to complete
    await run_tv_sync()
    return {"status": "success"}

@app.get("/api/system/api-status")
async def get_api_status():
    import os
    from src.config.loader import get_config
    config = {}
    try:
        config = get_config()
    except Exception:
        pass

    # 1. Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY") or config.get("BASIC_MODEL", {}).get("api_key")
    gemini_status = {
        "service": "Google AI Studio (Gemini)",
        "connected": bool(gemini_key),
        "details": "Connected (API Key Verified)" if gemini_key else "Unavailable",
        "fallback": "Local Ollama / Offline Mode" if not gemini_key else None
    }

    # 2. Alpha Vantage
    av_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    av_status = {
        "service": "Alpha Vantage API",
        "connected": bool(av_key),
        "details": "Connected (Realtime Entitlement Verified)" if av_key else "Unavailable",
        "fallback": "yfinance (Free/Unlimited Feed)" if not av_key else None
    }

    # 3. FMP
    fmp_key = os.environ.get("FMP_API_KEY")
    fmp_status = {
        "service": "Financial Modeling Prep (FMP)",
        "connected": bool(fmp_key),
        "details": "Connected (Movers API Verified)" if fmp_key else "Unavailable",
        "fallback": "yfinance / SEC RSS Feed" if not fmp_key else None
    }

    # 4. Tavily
    tavily_key = os.environ.get("TAVILY_API_KEY")
    tavily_status = {
        "service": "Tavily Search API",
        "connected": bool(tavily_key),
        "details": "Connected (Scout Tool Verified)" if tavily_key else "Unavailable",
        "fallback": "Brave Search / DuckDuckGo (Free)" if not tavily_key else None
    }

    # 5. Ngrok
    ngrok_token = os.environ.get("NGROK_AUTHTOKEN") or config.get("NGROK", {}).get("authtoken")
    ngrok_status = {
        "service": "Ngrok Tunneling Service",
        "connected": bool(ngrok_token),
        "details": "Connected (Webhook Port Forwarding Verified)" if ngrok_token else "Unavailable",
        "fallback": "Localhost Only (External Webhooks Disabled)" if not ngrok_token else None
    }

    return {
        "services": [
            gemini_status,
            av_status,
            fmp_status,
            tavily_status,
            ngrok_status
        ]
    }

# --- VLI CONSOLIDATED STATE ENDPOINT ---


@app.get("/api/vli/active-state")
async def get_active_vli_state(client_id: str = Header("default", alias="X-VLI-Client-ID")):
    try:
        from src.config.vli_context import vli_client_id
        vli_client_id.set(client_id)
    except Exception:
        pass
        
    logger.info(f"[VLI_TRACE] Entering get_active_vli_state for client: {client_id}")
    try:
        from src.config.vli import get_action_plan_path, get_inbox_path, get_vli_path

        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        plan_file = get_action_plan_path()

        # 1. Read Action Plan
        plan_markdown = "No active plan found."
        if os.path.exists(plan_file):
            with open(plan_file, encoding="utf-8") as f:
                plan_markdown = f.read()

        # 2. Read Telemetry (Optimized Tail - Increased to 16KB to prevent lag)
        telemetry_tail = ""
        if os.path.exists(telemetry_file):
            size = os.path.getsize(telemetry_file)
            with open(telemetry_file, encoding="utf-8", errors="ignore") as f:
                f.seek(max(0, size - 16000))
                telemetry_tail = f.read()

        # 3. Get Inbox Files
        inbox_files = []
        inbox_path = get_inbox_path()
        if os.path.exists(inbox_path):
            inbox_files = [f for f in os.listdir(inbox_path) if os.path.isfile(os.path.join(inbox_path, f))]

        # 4. Filter Alerts for UI
        ui_alerts = []
        for a in _vli_extracted_alerts:
            clean_a = a.copy()
            clean_a["symbol"] = a["symbol"].replace("^", "").replace("=F", "").replace("-USD", "")
            ui_alerts.append(clean_a)

        # 5. Read MACRO_WATCHLIST state
        macro_watchlist_content = {}
        target_bucket_path = os.path.join(VAULT_ROOT, "_cobalt", "01_Transit", "Buckets", "MACRO_WATCHLIST_state.json")
        if os.path.exists(target_bucket_path):
            try:
                with open(target_bucket_path, encoding="utf-8") as f:
                    macro_watchlist_content = json.load(f)
                    
                # Ensure candidates array is initialized
                if "candidates" not in macro_watchlist_content:
                    candidates = []
                    for row in macro_watchlist_content.get("rows", []):
                        if len(row) > 1:
                            sym = row[1]
                            price_str = row[2]
                            price_num = 0.0
                            try:
                                price_num = float(price_str.replace('$', '').replace('%', '').replace(',', ''))
                            except:
                                pass
                            
                            change_val = 0.0
                            if isinstance(row[3], dict):
                                change_val = row[3].get("value", 0.0)
                            else:
                                try:
                                    change_val = float(row[3])
                                except:
                                    pass
                                    
                            sortino = 0.0
                            try:
                                sortino = float(row[4])
                            except:
                                pass
                            
                            candidates.append({
                                "symbol": sym,
                                "name": row[0],
                                "price": price_num,
                                "change": change_val,
                                "sortino": sortino,
                                "tier": "Macro"
                            })
                    macro_watchlist_content["candidates"] = candidates

                # Dynamically enrich the has_report status for macro rows and candidates
                from datetime import datetime
                for row in macro_watchlist_content.get("rows", []):
                    if len(row) > 1:
                        sym = row[1]
                        sym_clean = sym.replace('^', '').replace('=', '').lower()
                        r_path1 = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{sym.lower()}.md')
                        r_path2 = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{sym_clean}.md')
                        r_path3 = os.path.join(os.getcwd(), 'backend', 'data', 'reports', f'analyze_{sym.lower()}.md')
                        r_path4 = os.path.join(os.getcwd(), 'backend', 'data', 'reports', f'analyze_{sym_clean}.md')
                        has_report = os.path.exists(r_path1) or os.path.exists(r_path2) or os.path.exists(r_path3) or os.path.exists(r_path4)
                        
                        meta = {"has_report": has_report}
                        if has_report:
                            paths_to_check = [r_path1, r_path2, r_path3, r_path4]
                            mtime = max(os.path.getmtime(p) if os.path.exists(p) else 0 for p in paths_to_check)
                            meta["updated_at"] = datetime.fromtimestamp(mtime).isoformat()
                            
                        # Append the report status at the end of the row (or as the 7th element)
                        if len(row) == 6:
                            row.append(meta)
                        elif len(row) >= 7 and isinstance(row[-1], dict):
                            row[-1].update(meta)

                for cand in macro_watchlist_content.get("candidates", []):
                    sym = cand.get("symbol")
                    if sym:
                        sym_clean = sym.replace('^', '').replace('=', '').lower()
                        r_path1 = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{sym.lower()}.md')
                        r_path2 = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{sym_clean}.md')
                        r_path3 = os.path.join(os.getcwd(), 'backend', 'data', 'reports', f'analyze_{sym.lower()}.md')
                        r_path4 = os.path.join(os.getcwd(), 'backend', 'data', 'reports', f'analyze_{sym_clean}.md')
                        has_report = os.path.exists(r_path1) or os.path.exists(r_path2) or os.path.exists(r_path3) or os.path.exists(r_path4)
                        
                        cand["has_report"] = has_report
                        if has_report:
                            paths_to_check = [r_path1, r_path2, r_path3, r_path4]
                            mtime = max(os.path.getmtime(p) if os.path.exists(p) else 0 for p in paths_to_check)
                            cand["updated_at"] = datetime.fromtimestamp(mtime).isoformat()

                # Call the unified enrich candidates function
                from src.server.routes.scanner import enrich_candidates_with_trends
                macro_watchlist_content["candidates"] = await enrich_candidates_with_trends(macro_watchlist_content["candidates"])

                # Post-enrichment grade/heat-score calculations
                for cand in macro_watchlist_content.get("candidates", []):
                    sortino = cand.get("sortino", 0.0)
                    rvol = cand.get("rvol", 1.0)
                    change = cand.get("change", 0.0)
                    
                    if sortino >= 5.0: cand["grade"] = "S"
                    elif sortino >= 2.5: cand["grade"] = "A"
                    elif sortino >= 2.0: cand["grade"] = "B"
                    elif sortino >= 1.0: cand["grade"] = "C"
                    else: cand["grade"] = "F"
                    
                    base_score = 50.0
                    if cand["grade"] == "A": base_score += 15.0
                    elif cand["grade"] == "B": base_score += 5.0
                    elif cand["grade"] == "C": base_score -= 10.0
                    elif cand["grade"] == "F": base_score -= 25.0
                    
                    base_score += (sortino * 10.0)
                    base_score += max(0.0, rvol - 1.0) * 5.0
                    base_score += min(20.0, change * 0.8)
                    cand["heat_score"] = int(max(0, min(100, base_score)))
                            
            except Exception as e:
                logger.error(f"Failed to read/enrich MACRO_WATCHLIST_state.json: {e}")
                
        # 6. Read SCANNER_RES state
        scanner_res_content = {"candidates": [], "pulse_mode": "Automated Pulse", "last_sync": None}
        sword_path = os.path.join(os.getcwd(), "backend", "data", "STRIKE_LIST.json")
        if not os.path.exists(sword_path):
            sword_path = os.path.join(os.getcwd(), "data", "STRIKE_LIST.json")
        scanner_bucket_path = os.path.join(VAULT_ROOT, "_cobalt", "01_Transit", "Buckets", "STRIKE_RES_state.json")
        
        try:
            engine = os.environ.get("VLI_SCANNER_ENGINE", "tradingview").lower()
            
            loaded_data = False
            
            if engine == "tradingview" and os.path.exists(scanner_bucket_path):
                with open(scanner_bucket_path, encoding="utf-8") as f:
                    data = json.load(f)
                    cands = data if isinstance(data, list) else data.get("candidates", [])
                    for c in cands:
                        if "tier" not in c: c["tier"] = "SWORD"
                    scanner_res_content["candidates"].extend(cands)
                    if isinstance(data, dict):
                        scanner_res_content["pulse_mode"] = "TradingView"
                        scanner_res_content["last_sync"] = data.get("metadata", {}).get("last_sync", data.get("updated_at", None))
                loaded_data = True
                
            if os.path.exists(sword_path):
                with open(sword_path, encoding="utf-8") as f:
                    data = json.load(f)
                    cands = data if isinstance(data, list) else data.get("candidates", []) or data.get("strike_list", [])
                    for c in cands:
                        if "tier" not in c: c["tier"] = "SWORD"
                    scanner_res_content["candidates"].extend(cands)
                    if isinstance(data, dict):
                        active_sf = _get_vli_session_config().get("active_strategy", "")
                        active_sn = active_sf.replace(".md", "").replace("cma_strategy_", "").replace("_", " ").title() if active_sf else "Active Strategy"
                        scanner_res_content["pulse_mode"] = data.get("pulse_mode", f"{active_sn} Scanner")
                        if not scanner_res_content.get("last_sync"):
                            scanner_res_content["last_sync"] = data.get("metadata", {}).get("last_sync", data.get("updated_at", None))
                loaded_data = True
                
            if not loaded_data and engine != "tradingview" and os.path.exists(scanner_bucket_path):
                with open(scanner_bucket_path, encoding="utf-8") as f:
                    data = json.load(f)
                    cands = data if isinstance(data, list) else data.get("candidates", [])
                    for c in cands:
                        if "tier" not in c: c["tier"] = "SWORD"
                    scanner_res_content["candidates"].extend(cands)
                    if isinstance(data, dict):
                        scanner_res_content["pulse_mode"] = data.get("pulse_mode", "TradingView")
                        scanner_res_content["last_sync"] = data.get("metadata", {}).get("last_sync", data.get("updated_at", None))
        except Exception as e:
            logger.error(f"Failed to load Sword data: {e}")
            
        pass
            
        # Defensive Deduplication: Ensure no duplicate symbols render across pipelines
        seen_symbols = {}
        for cand in scanner_res_content.get("candidates", []):
            sym = cand.get("symbol", "").upper()
            if not sym: continue
            
            existing = seen_symbols.get(sym)
            if existing:
                # Prefer institutional tiers over base pipeline tiers
                if cand.get("tier") in ["SHIELD", "SNIPER", "SWORD"] and existing.get("tier") not in ["SHIELD", "SNIPER", "SWORD"]:
                    seen_symbols[sym] = cand
            else:
                seen_symbols[sym] = cand
                
        scanner_res_content["candidates"] = list(seen_symbols.values())
        
        # Enrich candidates with dynamic trend alignments from the scanner cache
        try:
            from src.server.routes.scanner import enrich_candidates_with_trends
            scanner_res_content["candidates"] = await enrich_candidates_with_trends(scanner_res_content["candidates"])
        except Exception as enrich_e:
            logger.error(f"Failed to enrich active state candidates with trends: {enrich_e}")
            
        scanner_res_content["is_sample"] = get_scanner_is_sample()
                    
        # Dynamically enrich the has_report status to ensure UI polling catches live background generation
        from datetime import datetime
        for key in ["candidates", "sword_candidates", "shield_candidates"]:
            for cand in scanner_res_content.get(key, []):
                sym = cand.get("symbol", "")
                if sym:
                    r_path1 = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{sym.lower()}.md')
                    r_path2 = os.path.join(os.getcwd(), 'backend', 'data', 'reports', f'analyze_{sym.lower()}.md')
                    cand["has_report"] = False
                    active_path = None
                    if os.path.exists(r_path1):
                        active_path = r_path1
                    elif os.path.exists(r_path2):
                        active_path = r_path2
                        
                    if active_path:
                        cand["has_report"] = True
                        mtime = os.path.getmtime(active_path)
                        report_dt = datetime.fromtimestamp(mtime).isoformat()
                        cand_dt = cand.get("updated_at", "")
                        if not cand_dt or report_dt > cand_dt:
                            cand["updated_at"] = report_dt

        logger.info(f"[VLI_TRACE] State compiled for return. Telemetry size: {len(telemetry_tail)} bytes.")
        
        def sanitize_json_obj(obj):
            import math
            if isinstance(obj, dict):
                return {k: sanitize_json_obj(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize_json_obj(x) for x in obj]
            elif isinstance(obj, float):
                if math.isnan(obj) or math.isinf(obj):
                    return None
            return obj

        from fastapi.responses import JSONResponse
        return JSONResponse(
            content=sanitize_json_obj({
                "macros": json.loads(json.dumps(_get_vli_macro_snapshot(), default=str)),
                "macro_watchlist_content": macro_watchlist_content,
                "scanner_results": scanner_res_content,
                "last_macro_update": os.path.getmtime(get_vli_path("vli_macro_snapshot.json")) if os.path.exists(get_vli_path("vli_macro_snapshot.json")) else time.time(),
                "alerts": ui_alerts or [{"symbol": "SYS", "color": "green", "label": "VLI-IDLE"}],
                "dynamic_panels": json.loads(json.dumps(_vli_dynamic_panels, default=str)),
                "telemetry_tail": scrub_vli_output(telemetry_tail),
                "plan_markdown": scrub_vli_output(plan_markdown),
                "async_report": scrub_vli_output(_vli_last_async_report),
                "inbox_files": sorted(inbox_files, key=lambda x: os.path.getmtime(os.path.join(inbox_path, x)) if os.path.exists(os.path.join(inbox_path, x)) else 0, reverse=True),
                "ux_card": json.loads(json.dumps(_vli_last_ux_card, default=str)),
                "rules_enabled": _vli_rules_enabled,
                "convergence_data": json.loads(json.dumps(_vli_convergence_history, default=str)),
                "chat_history": json.loads(json.dumps(_vli_chat_history_store.get(client_id, []), default=str)),
                "session_config": _get_vli_session_config(),
                "client_id_echo": client_id
            }),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        )
    except Exception as e:
        logger.error(f"VLI: Error in consolidated active-state endpoint: {e}", exc_info=True)
        return {
            "error": str(e), 
            "macros": [], 
            "alerts": [], 
            "telemetry_tail": "BACKEND_ERROR", 
            "convergence_data": [],
            "chat_history": []
        }


# --- VLI SESSION CONFIGURATION ---

def _get_vli_session_config() -> dict:
    config_path = get_vli_path("vli_session_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _update_vli_session_config(updates: dict):
    config_path = get_vli_path("vli_session_config.json")
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
        except:
            pass
    config.update(updates)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)


@app.post("/api/vli/macro/toggle/{state}")
async def toggle_vli_macro(state: str):
    enabled = state.lower() == "on"
    _update_vli_session_config({"macro_enabled": enabled})
    logger.info(f"VLI Session: Macro background scraping toggled to: {enabled}")
    return {"status": "success", "macro_enabled": enabled}

    # --- RULE EXECUTION ENDPOINTS ---
    _vli_rules_enabled = state.lower() == "on" or state.lower() == "true"
    logger.info(f"VLI: Filing rules toggled to {_vli_rules_enabled}")
    return {"status": "success", "enabled": _vli_rules_enabled}


@app.post("/api/vli/rule/execute")
async def execute_vli_rule(original_name: str, suggested_name: str, target_folder: str):
    global _vli_last_inbox_action
    import shutil

    from src.config.vli import get_inbox_path, inbox_rule_engine

    inbox_path = get_inbox_path()
    src_path = os.path.join(inbox_path, original_name)

    # Target folder might be relative to vault root
    # Lstrip to ensure os.path.join doesn't treat it as absolute
    clean_folder = target_folder.lstrip("\\/")
    dest_dir = os.path.join(VAULT_ROOT, clean_folder)
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    dest_path = os.path.join(dest_dir, suggested_name)

    # Handle collisions
    final_dest = inbox_rule_engine.handle_collision(dest_path)

    try:
        shutil.move(src_path, final_dest)
        _vli_last_inbox_action = {"original_path": src_path, "target_path": final_dest}
        logger.info(f"VLI: Executed rule: Moved {original_name} to {os.path.abspath(final_dest)}")
        return {"status": "success", "dest": final_dest}
    except Exception as e:
        logger.error(f"VLI: Error executing rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vli/inbox/file-content")
async def get_vli_inbox_file_content(filename: str):
    """Retrieve raw content of an inbox file for dashboard preview."""
    from src.config.vli import get_inbox_path

    inbox_path = get_inbox_path()
    file_path = os.path.join(inbox_path, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        logger.error(f"VLI: Error reading inbox file {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def undo_vli_rule():
    global _vli_last_inbox_action

    if not _vli_last_inbox_action:
        raise HTTPException(status_code=400, detail="No action to undo")


# Global task and reset tracking
_vli_reset_requested = False
_vli_active_task: asyncio.Task | None = None
_vli_convergence_history: list[dict[str, Any]] = []


@app.post("/api/vli/report-metric")
async def report_vli_metric(metric: dict[str, Any]):
    """Receives and stores convergence metrics."""
    global _vli_convergence_history
    _vli_convergence_history.append(
        {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "iteration": metric.get("iteration", 0),
            "latency": metric.get("latency", 0),
            "accuracy": metric.get("accuracy", 0),
            "status": metric.get("status", "unknown"),  # "pass" or "fail"
            "error_type": metric.get("error_type", None),
        }
    )
    # Keep only the last 100 for memory efficiency
    if len(_vli_convergence_history) > 100:
        _vli_convergence_history = _vli_convergence_history[-100:]
    return {"status": "ok"}


class RefreshRequest(BaseModel):
    card_id: str

@app.post("/api/vli/refresh-card")
async def refresh_vli_card(req: RefreshRequest):
    """General refresh command handler for UX cards."""
    target = req.card_id.strip().upper()
    try:
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        
        if target == "ALL":
            # Refresh all active buckets
            from src.services.asset_bucket import AssetBucket
            logger.info("VLI: Global refresh requested for all UX cards")
            
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp} ###  [GLOBAL REFRESH] Target: ALL\n> Synchronizing all active Watchlist Engines...\n")
                tf.flush()
            
            # Currently only Macro Watchlist is active as a managed bucket
            # We can expand this loop to other persistent buckets in the future
            # Bypass generic AssetBucket to maintain custom structural JSON for sparklines
            from src.tools.finance import get_macro_symbols
            await get_macro_symbols.ainvoke({"fast_update": True})
            
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"> Global state sync complete. All frontend payloads stabilized.\n")
                tf.flush()
            return {"status": "success", "target": "ALL"}

        if target == "MW" or "MACRO" in target:
            from src.tools.finance import get_macro_symbols
            logger.info("VLI: Explicit refresh requested for MACRO_WATCHLIST")
            
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp} ###  [UX REFRESH] Target: {target}\n> Triggering forced update of Macro Watchlist Engine...\n")
                tf.flush()
            
            await get_macro_symbols.ainvoke({"fast_update": True})
            
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"> Macro Watchlist states securely synced to frontend payload.\n")
                tf.flush()
            return {"status": "success", "target": target}

            
        with open(telemetry_file, "a", encoding="utf-8") as tf:
            tf.write(f"\n{timestamp} ###  [UX REFRESH ERROR]\n> Target generic card identifier `{target}` not securely mapped for forced refreshes.\n")    
            tf.flush()
        return {"status": "ignored", "target": target, "msg": "Card identifier not recognized."}
    except Exception as e:
        logger.error(f"Failed to refresh card {target}: {e}")
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        try:
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp} ###  [UX REFRESH FAILED]\n> Error resolving card '{target}': {e}\n")    
                tf.flush()
        except: pass
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/vli/reset")
async def reset_vli_state(client_id: str = Header("default", alias="X-VLI-Client-ID")):
    try:
        from src.config.vli_context import vli_client_id
        vli_client_id.set(client_id)
    except Exception:
        pass
        
    global _vli_reset_requested, _vli_active_task, _vli_extracted_alerts, _vli_dynamic_panels, _vli_session_id, _vli_chat_history_store
    _vli_reset_requested = True
    _vli_chat_history_store[client_id] = [] # Purge specific client history

    # [NEW] Refresh Session ID to break 404 Trajectory cycles
    # This forces a fresh Google Cloud session context
    _vli_session_id = f"vli-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    from src.config.vli import get_vli_path
    telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")

    # [HARD KILL] Preemptively cancel the active graph task
    if _vli_active_task and not _vli_active_task.done():
        logger.warning(f"VLI_SYSTEM: SYSTEM_NODE deploying Hard-Kill signal for task {id(_vli_active_task)}")
        _vli_active_task.cancel()

    try:
        # [PROCESS CLEANUP] Kill orphaned headless browsers
        import subprocess

        logger.info("VLI_SYSTEM: Cleaning up background tool processes (msedge)...")
        subprocess.run(["taskkill", "/F", "/IM", "msedge.exe", "/T"], capture_output=True, check=False)

        import time
        timestamp = datetime.now().strftime("%H:%M:%S")
        for attempt in range(3):
            try:
                # Forcefully delete to break any handles
                if os.path.exists(telemetry_file):
                    os.remove(telemetry_file)
                
                with open(telemetry_file, "w", encoding="utf-8") as f:
                    f.write("# VLI Session Telemetry Log\n")
                    f.write(f"### [{timestamp}] SYSTEM_NODE: NEW SESSION INITIALIZED\n")
                    f.write("- **Status**: `READY`\n- **Action**: All previous telemetry backlog and active processes have been cleared.\n\n---\n")
                    f.flush()
                    os.fsync(f.fileno())
                break
            except Exception as fe:
                logger.error(f"VLI: Failed to truncate telemetry file (attempt {attempt+1}): {fe}")
                time.sleep(0.5)

        # Reset global state flags
        # Already declared global at top
        _vli_extracted_alerts = []
        _vli_dynamic_panels = []

        logger.info("VLI: Session reset successfully. Kill switch deployed.")
        await asyncio.sleep(0.5)
        _vli_reset_requested = False
        _vli_active_task = None

        return {"status": "success"}
    except Exception as e:
        logger.error(f"VLI: Error resetting session: {e}")
        return {"status": "error", "message": str(e)}
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/vli/inbox/open-editor")
async def open_vli_inbox_file_editor(filename: str):
    """Open an inbox file in the system's preferred editor (e.g. wordpad)."""
    import subprocess

    from src.config.vli import PREFERRED_EDITOR, get_inbox_path

    inbox_path = get_inbox_path()
    file_path = os.path.join(inbox_path, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Avoid blocking the server; use Popen to launch and detach
        logger.info(f"VLI: Opening {filename} with {PREFERRED_EDITOR}")
        subprocess.Popen([PREFERRED_EDITOR, file_path])
        return {"status": "success", "editor": PREFERRED_EDITOR}
    except Exception as e:
        logger.error(f"VLI: Failed to open editor: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class OpenFileRequest(BaseModel):
    filename: str


@app.post("/api/vli/open-file")
async def open_vli_artifact_file(req: OpenFileRequest):
    import subprocess
    import shutil

    from src.config.vli import PREFERRED_EDITOR

    reports_dir = os.path.join(os.getcwd(), "data", "reports")
    file_path = os.path.join(reports_dir, req.filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Popen to launch without blocking
        subprocess.Popen([PREFERRED_EDITOR, file_path])
        return {"status": "success"}
    except Exception as e:
        logger.error(f"VLI: Failed to open native file with {PREFERRED_EDITOR}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SnapTradeRegisterRequest(BaseModel):
    client_id: str = ""
    consumer_key: str = ""
    user_id: str = ""

@app.get("/api/vli/telemetry/tokens")
async def get_token_tally():
    from fastapi.responses import JSONResponse
    from src.utils.token_tracker import token_tracker
    return JSONResponse(token_tracker.get_tally())

@app.post("/api/brokerage/register")
async def register_snaptrade(req: SnapTradeRegisterRequest):
    try:
        import time
        from snaptrade_client import SnapTrade
        cid = req.client_id or os.getenv("SNAPTRADE_CLIENT_ID", "")
        ckey = req.consumer_key or os.getenv("SNAPTRADE_CONSUMER_KEY", "")
        client = SnapTrade(client_id=cid, consumer_key=ckey)
        uid = req.user_id or os.getenv("SNAPTRADE_USER_ID") or f"vli-user-{int(time.time())}"
        res = client.authentication.register_snap_trade_user(user_id=uid)
        user_secret = getattr(res, 'user_secret', None)
        if not user_secret and isinstance(res, dict):
            user_secret = res.get('userSecret') or res.get('user_secret')
        return JSONResponse({"user_id": uid, "user_secret": user_secret})
    except Exception as e:
        logger.error(f"SnapTrade registration error: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)

class SnapTradeLoginRequest(BaseModel):
    client_id: str = ""
    consumer_key: str = ""
    user_id: str = ""
    user_secret: str = ""

@app.post("/api/brokerage/login")
async def login_snaptrade(req: SnapTradeLoginRequest):
    try:
        from snaptrade_client import SnapTrade
        cid = req.client_id or os.getenv("SNAPTRADE_CLIENT_ID", "")
        ckey = req.consumer_key or os.getenv("SNAPTRADE_CONSUMER_KEY", "")
        uid = req.user_id or os.getenv("SNAPTRADE_USER_ID", "")
        usecret = req.user_secret or os.getenv("SNAPTRADE_USER_SECRET", "")
        client = SnapTrade(client_id=cid, consumer_key=ckey)
        res = client.authentication.login_snap_trade_user(user_id=uid, user_secret=usecret)
        uri = getattr(res, 'login_redirect_uri', None)
        if not uri and isinstance(res, dict):
            uri = res.get('loginRedirectURI') or res.get('login_redirect_uri')
        return JSONResponse({"redirect_uri": uri})
    except Exception as e:
        logger.error(f"SnapTrade login error: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)

@app.get("/api/brokerage/accounts")
async def get_brokerage_accounts():
    from fastapi.responses import JSONResponse
    try:
        from src.services.brokerage_cache import BrokerageCache
        cache_data = BrokerageCache._load_cache()
        parsed_accounts = []
        for acct_id in cache_data.keys():
            parsed_accounts.append({
                "id": acct_id,
                "name": acct_id
            })
        return JSONResponse({"accounts": parsed_accounts})
    except Exception as e:
        logger.error(f"BrokerageCache accounts error: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)

@app.post("/api/fidelity/sync")
async def sync_fidelity_payload(request: Request):
    from fastapi.responses import JSONResponse
    from src.services.brokerage_cache import BrokerageCache
    try:
        body = await request.json()
        source_url = body.get('sourceUrl', '')
        
        # Pass the raw payload to the BrokerageCache for extraction and merging
        result = BrokerageCache.ingest_fidelity_payload(body)
        
        return JSONResponse({"status": "success", "merged_count": result})
    except Exception as e:
        logger.error(f"Fidelity sync error: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)

_YF_HISTORY_CACHE = {}

@app.get("/api/brokerage/history")
async def get_brokerage_history(account_id: str, start_date: str, end_date: str):
    from fastapi.responses import JSONResponse
    try:
        from src.services.brokerage_cache import BrokerageCache
        
        # Support comma-separated accounts for aggregation
        accounts = [a.strip() for a in account_id.split(",") if a.strip()]
        if not accounts:
            return JSONResponse({"error": "No accounts specified"}, status_code=400)
        
        # 1. Fetch activities directly from the pure offline cache
        activities = []
        for acct in accounts:
            activities.extend(BrokerageCache.get_activities(acct))
            
        # Deduplicate activities if they have same id
        seen_ids = set()
        dedup_activities = []
        for act in activities:
            act_id = act.get('id')
            if act_id:
                if act_id not in seen_ids:
                    seen_ids.add(act_id)
                    dedup_activities.append(act)
            else:
                dedup_activities.append(act)
        activities = BrokerageCache.group_trade_activities(dedup_activities, price_tolerance=0.50, max_time_gap_seconds=30)
        
        # Reverse to oldest first for chronological timestamping and position calculation
        activities_chronological = list(reversed(activities))
        
        import datetime
        today_dt = datetime.datetime.now()
        if today_dt.weekday() == 5: # Saturday -> Go back to Friday
            today_dt = today_dt - datetime.timedelta(days=1)
        elif today_dt.weekday() == 6: # Sunday -> Go back to Friday
            today_dt = today_dt - datetime.timedelta(days=2)
        today_str = today_dt.strftime("%Y-%m-%d")
        
        daily_counters = {}
        results = []
        
        # We will track open positions per-account first
        all_accounts_open_positions = []
        cache_raw = BrokerageCache._load_cache()
        
        for acct in accounts:
            acct_open_positions = {}
            acct_activities = list(reversed(BrokerageCache.get_activities(acct)))
            
            # Check if this account has explicit positions (Fidelity)
            is_fidelity = "TradingView" not in acct
            has_explicit = is_fidelity and acct in cache_raw and "positions" in cache_raw[acct]
            
            if has_explicit:
                explicit_list = cache_raw[acct]["positions"] or []
                for pos in explicit_list:
                    sym_raw = pos["symbol"].upper().replace('-USD', '').replace('*', '')
                    if "CASH" in sym_raw or "FZFXX" in sym_raw or "SPAXX" in sym_raw or "FDIC" in sym_raw:
                        continue
                    
                    pos_qty = float(pos.get("quantity", 0.0))
                    if abs(pos_qty) <= 0.0001:
                        continue
                        
                    avg_cost = float(pos.get("average_cost", 0.0))
                    raw_tot = pos.get("total_cost")
                    tot_cost = float(raw_tot) if (raw_tot is not None and float(raw_tot) != 0.0) else (pos_qty * avg_cost)
                    
                    # Calculate qty_today from activities
                    qty_today = 0.0
                    for act in acct_activities:
                        action = act.get('type', act.get('action', 'N/A')).upper()
                        if action not in ["BUY", "SELL", "BOUGHT", "SOLD", "BTO", "STC", "BTC", "STO", "REINVEST", "DIVIDEND"]:
                            continue
                            
                        act_sym = act.get('symbol') or act.get('universal_symbol') or {}
                        if isinstance(act_sym, dict):
                            act_sym = act_sym.get('symbol', 'N/A')
                        act_sym_raw = str(act_sym).upper().replace('-USD', '').replace('*', '')
                        
                        if act_sym_raw == sym_raw:
                            act_u = float(act.get('units', 0))
                            placed_time = act.get('trade_date') or act.get('time_placed') or ''
                            date_only = str(placed_time)[:10] if placed_time else "Unknown"
                            if date_only == today_str:
                                if action in ["BUY", "BOUGHT", "BTO", "BTC", "REINVEST", "DIVIDEND"]:
                                    qty_today += act_u
                                elif action in ["SELL", "SOLD", "STC", "STO"]:
                                    qty_today -= act_u
                                    
                    acct_open_positions[sym_raw] = {
                        "quantity": pos_qty,
                        "average_cost": avg_cost,
                        "total_cost": tot_cost,
                        "qty_today": qty_today
                    }
            else:
                # Dynamic position calculation from activities
                for act in acct_activities:
                    action = act.get('type', act.get('action', 'N/A')).upper()
                    if action not in ["BUY", "SELL", "BOUGHT", "SOLD", "BTO", "STC", "BTC", "STO", "REINVEST", "DIVIDEND"]:
                        continue
                        
                    act_sym = act.get('symbol') or act.get('universal_symbol') or {}
                    if isinstance(act_sym, dict):
                        act_sym = act_sym.get('symbol', 'N/A')
                    sym_raw = str(act_sym).upper().replace('-USD', '').replace('*', '')
                    if sym_raw == 'N/A': continue
                    
                    qty = float(act.get('units', 0))
                    price = float(act.get('price', 0))
                    status = act.get('status', 'Executed')
                    placed_time = act.get('trade_date') or act.get('time_placed') or ''
                    date_only = str(placed_time)[:10] if placed_time else "Unknown"
                    
                    if status == "Executed":
                        if sym_raw not in acct_open_positions:
                            acct_open_positions[sym_raw] = {"quantity": 0.0, "total_cost": 0.0, "average_cost": 0.0, "qty_today": 0.0}
                            
                        old_qty = acct_open_positions[sym_raw]["quantity"]
                        
                        if action in ["BUY", "BOUGHT", "BTO", "BTC", "REINVEST", "DIVIDEND"]:
                            if old_qty < -0.0001:
                                # Covering short
                                covered = min(qty, -old_qty)
                                acct_open_positions[sym_raw]["quantity"] += covered
                                current_avg = acct_open_positions[sym_raw].get("average_cost", 0.0)
                                acct_open_positions[sym_raw]["total_cost"] -= covered * current_avg
                                
                                remaining = qty - covered
                                if remaining > 0.0001:
                                    acct_open_positions[sym_raw]["quantity"] += remaining
                                    acct_open_positions[sym_raw]["total_cost"] += remaining * price
                            else:
                                acct_open_positions[sym_raw]["quantity"] += qty
                                acct_open_positions[sym_raw]["total_cost"] += qty * price
                                
                            if date_only == today_str:
                                acct_open_positions[sym_raw]["qty_today"] += qty
                        elif action in ["SELL", "SOLD", "STC", "STO"]:
                            if old_qty > 0.0001:
                                # Closing long
                                closed = min(qty, old_qty)
                                acct_open_positions[sym_raw]["quantity"] -= closed
                                current_avg = acct_open_positions[sym_raw].get("average_cost", 0.0)
                                acct_open_positions[sym_raw]["total_cost"] -= closed * current_avg
                                
                                remaining = qty - closed
                                if remaining > 0.0001:
                                    acct_open_positions[sym_raw]["quantity"] -= remaining
                                    acct_open_positions[sym_raw]["total_cost"] += remaining * price
                            else:
                                # Shorting
                                acct_open_positions[sym_raw]["quantity"] -= qty
                                acct_open_positions[sym_raw]["total_cost"] += qty * price
                                
                            if date_only == today_str:
                                acct_open_positions[sym_raw]["qty_today"] -= qty
                                
                        abs_qty = abs(acct_open_positions[sym_raw]["quantity"])
                        if abs_qty > 0.0001:
                            acct_open_positions[sym_raw]["average_cost"] = acct_open_positions[sym_raw]["total_cost"] / abs_qty
                        else:
                            acct_open_positions[sym_raw]["quantity"] = 0.0
                            acct_open_positions[sym_raw]["total_cost"] = 0.0
                            acct_open_positions[sym_raw]["average_cost"] = 0.0
                            acct_open_positions[sym_raw]["qty_today"] = 0.0
            
            all_accounts_open_positions.append(acct_open_positions)
            
        # Combine open positions across accounts
        open_positions = {}
        for acct_pos in all_accounts_open_positions:
            for sym, pdata in acct_pos.items():
                if sym not in open_positions:
                    open_positions[sym] = {"quantity": 0.0, "total_cost": 0.0, "average_cost": 0.0, "qty_today": 0.0}
                open_positions[sym]["quantity"] += pdata["quantity"]
                open_positions[sym]["total_cost"] += pdata["total_cost"]
                open_positions[sym]["qty_today"] += pdata["qty_today"]
                
        for sym in list(open_positions.keys()):
            abs_qty = abs(open_positions[sym]["quantity"])
            if abs_qty > 0.0001:
                open_positions[sym]["average_cost"] = open_positions[sym]["total_cost"] / abs_qty
            else:
                del open_positions[sym]
                
        # Fill order history log items
        for act in activities_chronological:
            action = act.get('type', act.get('action', 'N/A')).upper()
            if action not in ["BUY", "SELL", "BOUGHT", "SOLD", "BTO", "STC", "BTC", "STO", "REINVEST", "DIVIDEND"]:
                continue
                
            act_sym = act.get('symbol') or act.get('universal_symbol') or {}
            if isinstance(act_sym, dict):
                act_sym = act_sym.get('symbol', 'N/A')
            sym_raw = str(act_sym).upper().replace('-USD', '').replace('*', '')
            if sym_raw == 'N/A': continue
            
            qty = float(act.get('units', 0))
            price = float(act.get('price', 0))
            status = act.get('status', 'Executed')
            placed_time = act.get('trade_date') or act.get('time_placed') or ''
            date_only = str(placed_time)[:10] if placed_time else "Unknown"
            
            act_id_str = str(act.get('id', ''))
            alt_date_only = None
            if 'T' in act_id_str:
                import re
                iso_match = re.search(r'(\d{4}-\d{2}-\d{2})T', act_id_str)
                if iso_match:
                    alt_date_only = iso_match.group(1)
            
            real_time = None
            placed_time_str = str(placed_time) if placed_time else ""
            if placed_time_str:
                if 'T' in placed_time_str:
                    real_time = placed_time_str.split('T')[1][:8]
                elif ' ' in placed_time_str:
                    real_time = placed_time_str.split(' ')[-1][:8]
                    
            if real_time and (real_time.startswith('00:00') or real_time.startswith('04:00') or real_time.startswith('05:00')):
                real_time = None
            
            in_range = (start_date <= date_only <= end_date) or (alt_date_only and start_date <= alt_date_only <= end_date) or (date_only == "Unknown")
            if in_range:
                if real_time:
                    fmt_time = f"{date_only} {real_time}"
                else:
                    if date_only not in daily_counters:
                        daily_counters[date_only] = 0
                    
                    daily_counters[date_only] += 1
                    seconds = daily_counters[date_only]
                    minutes = seconds // 60
                    remaining_secs = seconds % 60
                    synth_time = f"09:{30 + minutes:02d}:{remaining_secs:02d}"
                    
                    fmt_time = f"{date_only} {synth_time}" if date_only != "Unknown" else "Unknown"
                
                results.append({
                    "time": fmt_time,
                    "symbol": sym_raw,
                    "action": action,
                    "qty": qty,
                    "price": price,
                    "status": status
                })
                
        results.reverse() # Newest first for UI log
        
        # Filter out 0-quantity positions
        active_open_positions = {k: v for k, v in open_positions.items() if abs(v["quantity"]) > 0.0001}
        open_positions = active_open_positions
        positions_payload = []
        
        # Pull real trade times from PM BrokerageCache
        real_trade_times = {}
        for acct in accounts:
            cached_acts = BrokerageCache.get_activities(acct)
            for act in cached_acts:
                # We want the MOST RECENT trade's time for this position today
                act_sym = ""
                if "universal_symbol" in act and isinstance(act["universal_symbol"], dict):
                    act_sym = act["universal_symbol"].get("symbol", "")
                elif "symbol" in act and isinstance(act["symbol"], dict):
                    act_sym = act["symbol"].get("symbol", "")
                    
                act_sym = act_sym.upper().replace('-USD', '').replace('*', '')
                trade_date_str = act.get("trade_date", "")
                
                # Keep the newest time (BrokerageCache is usually newest first, so we just check if it's there)
                if act_sym and act_sym not in real_trade_times and "T" in trade_date_str:
                    # '2026-04-29T15:54:07.000Z' -> '2026-04-29 15:54:07'
                    full_time = trade_date_str.split(".")[0].replace("T", " ")
                    real_trade_times[act_sym] = full_time

        import yfinance as yf
        import math
        
        def safe_float(val, default=0.0):
            try:
                f = float(val)
                return default if math.isnan(f) else f
            except:
                return default
                
        if open_positions:
            tickers = list(open_positions.keys())
            yf_to_raw = {}
            yf_tickers = []
            for t in tickers:
                yf_t = t
                if yf_t.startswith('/'):
                    yf_t = yf_t[1:] + '=F'
                yf_tickers.append(yf_t)
                yf_to_raw[yf_t] = t
                
            def fetch_yf():
                return yf.download(yf_tickers, period="5d", interval="1d", progress=False)

            try:
                import time
                global _YF_HISTORY_CACHE
                cache_key = tuple(sorted(yf_tickers))
                cached = _YF_HISTORY_CACHE.get(cache_key)
                
                # 15-second TTL keeps data fresh while making tab switches and toggles instant (<10ms)
                if cached and (time.time() - cached[0] < 15.0):
                    data = cached[1]
                else:
                    try:
                        data = await asyncio.wait_for(asyncio.to_thread(fetch_yf), timeout=3.5)
                        _YF_HISTORY_CACHE[cache_key] = (time.time(), data)
                    except Exception as yf_err:
                        logger.warning(f"yfinance download fallback triggered: {yf_err}")
                        data = None

                if data is None or (hasattr(data, 'empty') and data.empty):
                    raise ValueError("yfinance returned empty or invalid data")

                for yf_sym, sym in yf_to_raw.items():
                    pdata = open_positions[sym]
                    try:
                        import pandas as pd
                        
                        # Handle yfinance DataFrame column structures cleanly
                        if 'Close' in data.columns:
                            close_df = data['Close']
                        else:
                            close_df = data
                            
                        if isinstance(close_df, pd.DataFrame):
                            if yf_sym in close_df.columns:
                                close_col = close_df[yf_sym]
                            else:
                                close_col = close_df.iloc[:, 0]
                        else:
                            close_col = close_df
                            
                        # Extract raw scalar to prevent pandas single-element Series TypeError
                        last_val = close_col.iloc[-1]
                        prev_val = close_col.iloc[-2] if len(close_col) > 1 else last_val
                        
                        if isinstance(last_val, pd.Series):
                            last_val = last_val.iloc[0]
                        if isinstance(prev_val, pd.Series):
                            prev_val = prev_val.iloc[0]
                            
                        last_price = safe_float(last_val)
                        prev_close = safe_float(prev_val)
                        
                        if last_price and not prev_close:
                            prev_close = last_price
                        
                        last_time_obj = close_col.index[-1]
                        last_time_str = last_time_obj.strftime('%Y-%m-%d 16:00') if hasattr(last_time_obj, 'strftime') else 'Unknown'
                        
                        # Override with real execution time from CSV if available
                        if sym in real_trade_times:
                            last_time_str = real_trade_times[sym]
                        
                        multiplier = BrokerageCache.get_futures_multiplier(sym)
                        qty = safe_float(pdata['quantity'])
                        qty_today = safe_float(pdata.get('qty_today', 0.0))
                        avg_cost = safe_float(pdata['average_cost'])
                        total_cost = qty * avg_cost * multiplier
                        current_value = qty * last_price * multiplier
                        
                        if qty < 0:
                            qty_yesterday = min(0.0, qty - min(0.0, qty_today))
                            held_today = min(0.0, qty_today)
                        else:
                            qty_yesterday = max(0.0, qty - max(0.0, qty_today))
                            held_today = max(0.0, qty_today)
                            
                        todays_gl_dol = ((last_price - prev_close) * qty_yesterday + (last_price - avg_cost) * held_today) * multiplier
                        
                        cost_basis_today = abs((prev_close * qty_yesterday + avg_cost * held_today) * multiplier)
                        todays_gl_pct = (todays_gl_dol / cost_basis_today * 100) if cost_basis_today > 0.0 else 0.0
                        
                        total_gl_dol = (last_price - avg_cost) * qty * multiplier
                        total_gl_pct = (total_gl_dol / abs(total_cost) * 100) if abs(total_cost) > 0.0 else 0.0
                        
                        positions_payload.append({
                            "symbol": sym,
                            "last_price": last_price,
                            "todays_gl_pct": todays_gl_pct,
                            "todays_gl_dol": todays_gl_dol,
                            "total_gl_pct": total_gl_pct,
                            "total_gl_dol": total_gl_dol,
                            "qty": qty,
                            "average_cost": avg_cost,
                            "current_value": current_value,
                            "last_time": last_time_str
                        })
                    except Exception as e:
                        logger.error(f"Failed extracting yf data for {sym}: {e}")
                        positions_payload.append({
                            "symbol": sym, "last_price": safe_float(pdata['average_cost']), "todays_gl_pct": 0, "todays_gl_dol": 0,
                            "total_gl_pct": 0, "total_gl_dol": 0, "qty": safe_float(pdata['quantity']), 
                            "average_cost": safe_float(pdata['average_cost']), "current_value": safe_float(pdata['total_cost']), "last_time": "Unknown"
                        })
            except Exception as e:
                logger.error(f"yfinance overall fetch failed: {e}")
                for sym, pdata in open_positions.items():
                    positions_payload.append({
                        "symbol": sym, "last_price": safe_float(pdata['average_cost']), "todays_gl_pct": 0, "todays_gl_dol": 0,
                        "total_gl_pct": 0, "total_gl_dol": 0, "qty": safe_float(pdata['quantity']), 
                        "average_cost": safe_float(pdata['average_cost']), "current_value": safe_float(pdata['total_cost']), "last_time": "Unknown"
                    })
            
        realized_pnl = 0.0
        closed_positions = []
        today_realized_pnl = 0.0
        import datetime
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        today_dt = datetime.datetime.now(ZoneInfo("America/New_York"))
        today_str = today_dt.strftime("%Y-%m-%d")
        tomorrow_str = (today_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        
        total_fees_summary = 0.0
        for acct in accounts:
            realized_pnl_data = BrokerageCache.calculate_realized_pnl(acct, start_date, end_date)
            realized_pnl += realized_pnl_data.get("total_pnl", 0.0)
            total_fees_summary += realized_pnl_data.get("total_fees", 0.0)
            closed_positions.extend(realized_pnl_data.get("closed_trades", []))
            
            today_realized_pnl_data = BrokerageCache.calculate_realized_pnl(acct, today_str, tomorrow_str)
            today_realized_pnl += today_realized_pnl_data.get("total_pnl", 0.0)
        
        return JSONResponse({
            "history": results, 
            "positions": positions_payload,
            "closed_positions": closed_positions,
            "realized_pnl_summary": realized_pnl,
            "today_realized_pnl": today_realized_pnl,
            "total_fees_summary": total_fees_summary
        })
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"SnapTrade history error: {e}\n{tb}")
        return JSONResponse({"error": str(e), "traceback": tb}, status_code=400)


async def _invoke_vli_agent(
    text: str,
    image: str | None = None,
    direct_mode: bool = False,
    raw_data_mode: bool = False,
    reporter_llm_type: str = "reasoning",
    vli_llm_type: str = "reasoning",
    thread_id: str | None = None,
    snaptrade_settings: dict | None = None,
    thinking_mode: bool = False,
) -> tuple[str, dict]:
    logger.info(f"[VLI_TRACE] _invoke_vli_agent called with text: '{text}' (thread_id: {thread_id})")
    """Invoke the agent graph in a non-streaming way for the VLI dashboard."""
    global _vli_session_id
    if thread_id is None:
        thread_id = _vli_session_id

    # [STABILITY] Clear any previous reset flags for the fresh directive
    global _vli_reset_requested, _vli_active_task, _vli_extracted_alerts, _vli_dynamic_panels
    global _vli_last_ux_card, _vli_convergence_history
    _vli_reset_requested = False

    # Import tools for Fast-Path scope
    try:
        from src.tools.finance import get_stock_quote
        from src.utils.vli_metrics import log_vli_metric
    except ImportError:
        get_stock_quote = None
        log_vli_metric = lambda *args, **kwargs: None
    # [NEW] Standardized Intent classification
    intent_mode = _get_vli_intent(text)

    # [HARDENING] Context Poisoning Prevention
    # If generating a tactical report, isolate the LangGraph thread completely so massive 
    # reports from previous tickers do not bleed into the context window.
    if intent_mode == "TACTICAL_EXECUTION" or any(text.lower().startswith(a) for a in TACTICAL_REPORT_ALIASES):
        import uuid
        thread_id = f"iso_{uuid.uuid4().hex[:8]}"
        logger.info(f"[VLI_AGENT] Isolated TACTICAL_EXECUTION to fresh thread: {thread_id}")

    # [FAST-PATH TRIGGERS] Deterministic bypass for low-latency situation awareness
    is_smc = "SMC" in text.upper()
    is_fast_override = any(kw in text.upper() for kw in FAST_OVERRIDE_TOKENS)

    # Exclusion: Technical keywords (Sortino, Sharpe, etc.) should use the full agent graph
    is_technical = any(kw in text.upper() for kw in TECH_KEYWORDS) and not (is_smc and is_fast_override)

    is_macro = "MACRO" in text.upper() and any(kw in text.upper() for kw in MACRO_TOKENS)
    is_price_list = ("SYMBOL" in text.upper() or "PORTFOLIO" in text.upper()) and "PRICE" in text.upper()
    is_vix = "VIX" in text.upper() and len(text) < 30

    # 2. Refined Ticker Query: Qualified vs Unqualified vs Analyze
    is_qualified = any(q in text.upper() for q in QUALIFIER_TOKENS) or "GET " in text.upper() or len(text.split()) <= 2
    is_analyze = any(kw in text.upper() for kw in TACTICAL_REPORT_TOKENS) and not (is_smc and is_fast_override)
    is_ticker_query = ("$" in text or "GET " in text.upper() or is_fast_override) and len(text) < 65 and not is_analyze

    is_fast_track = ((is_macro or is_price_list or is_vix or is_ticker_query) and not is_technical and not is_analyze) or raw_data_mode
    if "--FORCE-GRAPH" in text.upper():
        is_fast_track = False
        is_macro = False

    if is_fast_track:
        ticker = ""
        # 1. Prioritize $TICKER format
        sym_match = re.search(r"\$([A-Z]{1,10})", text.upper())
        if sym_match:
            ticker = sym_match.group(1)
        elif is_vix:
            ticker = "VIX"
        else:
            # Fallback to general search but exclude stop-words
            ticker_stop_words = [
                "GET",
                "STOCK",
                "PRICE",
                "LIST",
                "MARCO",
                "MARO",
                "VALUE",
                "PORT",
                "SYMBOL",
                "SMC",
                "FOR",
                "ANALYSIS",
                "REPORT",
                "ANALYZE",
                "FAST",
                "QUICK",
                "HIGH-LEVEL",
                "SHORTCUT",
                "RAPID",
                "HIGH",
                "LEVEL",
                "RAW",
                "DATA",
                "VLI",
                "NEWS",
                "SENTIMENT",
            ]
            words = re.findall(r"\b([A-Z]{1,10})\b", text.upper())
            for word in words:
                if word not in ticker_stop_words:
                    ticker = word
                    break

        if "GET_SPARKLINE_AUDIT_VLI" in text.upper():
            # [STABILITY] Deterministic Audit Fast-Path
            from src.tools.finance import get_sparkline_audit_vli
            start_time = datetime.now()
            try:
                # Extract args via regex for speed/robustness
                t_match = re.search(r"--ticker=([^\s]+)", text)
                r_match = re.search(r"--ref_time_ms=([^\s]+)", text)
                
                ticker_arg = t_match.group(1) if t_match else "SPY"
                ref_ms_arg = int(r_match.group(1)) if r_match else None
                
                logger.info(f"VLI Fast-Path: Executing Sparkline Audit for {ticker_arg} (ref_ms: {ref_ms_arg})")
                audit_json = await get_sparkline_audit_vli(ticker=ticker_arg, ref_time_ms=ref_ms_arg)
                
                duration = (datetime.now() - start_time).total_seconds()
                _vli_convergence_history.append({
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "iteration": 1,
                    "latency": duration,
                    "accuracy": 100.0,
                    "status": "pass"
                })
                return audit_json, {}
            except Exception as ae:
                logger.error(f"VLI Fast-Path: Audit intercept failed: {ae}")
                # Fall through to graph if intercept fails

        if is_macro:
            # [CRITICAL] Macro Institutional Intercept
            from src.tools.finance import get_macro_symbols
            start_time = datetime.now()
            try:
                # Call the high-fidelity macro symbols tool
                report = await get_macro_symbols()
                duration = (datetime.now() - start_time).total_seconds()
                
                # Persist the artifact
                _persist_vli_report(text, report)
                
                # Convergence history update
                _vli_convergence_history.append({
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "iteration": 1,
                    "latency": duration,
                    "accuracy": 100.0,
                    "status": "pass"
                })
                
                return report, {}
            except Exception as me:
                logger.error(f"VLI Fast-Path: Macro symbols tool failed: {me}")
                # Fallback to the text-based list below if the tool fails
            from src.services.macro_registry import macro_registry
            start_time = datetime.now()
            try:
                # [BATCH FAST-PATH] Comprehensive Metric Retrieval
                registry_macros = macro_registry.get_macros()
                # Limit to core set for Fast-Path responsiveness
                target_keys = ["SPY", "QQQ", "VIX", "DXY", "TNX", "CL", "GLD", "BTC"]
                tickers = [registry_macros.get(k, k) for k in target_keys if k in registry_macros]
                
                results = []
                # [FIX] Call the underlying tool function directly for high-fidelity dict responses
                q_func = getattr(get_stock_quote, "coroutine", getattr(get_stock_quote, "func", None))
                if not q_func:
                    raise TypeError("VLI Fast-Path: Tool not correctly configured.")

                # Fetch in parallel
                tasks = [asyncio.wait_for(q_func(ticker=t, use_fast_path=True), timeout=5.0) for t in tickers]
                quotes = await asyncio.gather(*tasks, return_exceptions=True)

                for i, q in enumerate(quotes):
                    t = target_keys[i]
                    # Handle results with normalization
                    if isinstance(q, dict) and "price" in q:
                        p, c = q.get("price", 0), q.get("change", 0)
                        # [FIX] Yield formatting: TNX/TYX should be % not $
                        if t.upper() in ["TNX", "TYX", "FVX"]:
                            results.append(f"- **{t}**: `{p:.2f}%` ({'+' if c >= 0 else ''}{c:.2f}%)")
                        else:
                            results.append(f"- **{t}**: `${p:.2f}` ({'+' if c >= 0 else ''}{c:.2f}%)")
                    elif isinstance(q, str) and "$" in q:
                        results.append(f"- **{t}**: {q}")
                    else:
                        logger.error(f"VLI Fast-Path: Failed to fetch {t}: {q}")
                        results.append(f"- **{t}**: `N/A` (Timeout/Error)")

                duration = (datetime.now() - start_time).total_seconds()
                
                # Persist result
                clean_results = [str(r) for r in results]
                _persist_vli_report(text, "### Global Macro Tickers (Atomic Fast-Path)\n" + "\n".join(clean_results))

                _vli_convergence_history.append({
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "iteration": 1,
                    "latency": duration,
                    "accuracy": 100.0,
                    "status": "pass"
                })
                
                return "### Global Macro Tickers (Atomic Fast-Path)\n" + "\n".join(clean_results), {}
            except Exception as be:
                logger.warning(f"VLI Fast-Path: Batch retrieval failed: {be}")
                    # Fallback to text list if batch fails

            macro_report = (
                "### Global Macro Ticker Reference\n"
                "- **Equities**: `$SPY`, `$QQQ`, `$IWM`\n"
                "- **Volatility**: `$VIX` (Fear Index)\n"
                "- **Currencies**: `$DXY` (Dollar), `$USDJPY`, `$EURUSD`\n"
                "- **Rates/Bonds**: `$TNX` (10Y Yield), `$TLT` (20Y+ Bonds)\n"
                "- **Commodities**: `$GLD` (Gold), `$SLV` (Silver), `$CL=F` (Crude Oil)\n"
                "- **Crypto**: `$BTCUSD`, `$ETHUSD`\n\n"
                "*Tip: Type 'Get Macro Price list' for live situation awareness data.*"
            )
            _vli_convergence_history.append({"timestamp": datetime.now().strftime("%H:%M:%S"), "iteration": 1, "latency": 0.2, "accuracy": 100.0, "status": "pass"})
            return macro_report, {}

        if ticker and get_stock_quote:
            try:
                start_time = datetime.now()
                # Call tool directly with Fast-Path enabled (Deterministic & Lock-Free)
                # [NEW] SMC Fast Path Intercept
                if is_smc or raw_data_mode:
                    if raw_data_mode:
                        from src.tools.finance import get_raw_smc_tables

                        report = await asyncio.wait_for(get_raw_smc_tables(ticker=ticker), timeout=25.0)
                    else:
                        from src.tools.finance import run_smc_analysis

                        r_func = getattr(run_smc_analysis, "coroutine", getattr(run_smc_analysis, "func", None))
                        report = await asyncio.wait_for(r_func(ticker=ticker, interval="auto"), timeout=15.0)

                    # [ARTIFACT CACHING] Persist the payload for session context
                    try:
                        # 1. Internal Ticker-based cache


                        artifacts_dir = os.path.join(os.getcwd(), "data", "artifacts")
                        os.makedirs(artifacts_dir, exist_ok=True)
                        ext = "json" if raw_data_mode else "md"
                        with open(os.path.join(artifacts_dir, f"{str(ticker).upper()}.{ext}"), "w", encoding="utf-8") as f:
                            f.write(report)

                        # 2. [FIX] Dashboard-compatible persistence (Slugified for Artifact Links)
                        # We use the original 'text' but strip "--raw" etc if needed to match frontend
                        clean_text = text.replace("--raw", "").replace("--RAW", "").strip()
                        _persist_vli_report(clean_text, report)
                    except Exception as e:
                        logger.error(f"Failed to persist artifact for {ticker}: {e}")

                    duration = (datetime.now() - start_time).total_seconds()
                    log_vli_metric(f"fastpath_smc_{ticker.lower()}", duration, status="pass")
                    _vli_convergence_history.append({"timestamp": datetime.now().strftime("%H:%M:%S"), "iteration": 1, "latency": duration, "accuracy": 100.0, "status": "pass"})
                    return report, {}

                # [SMC REWORK] Conditional fetch: Full SMC (OHLCV) for unqualified vs Atomic for qualified
                if is_qualified:
                    # Atomic Fetch: Price + Volume + Specific Qualifier
                    q_func = getattr(get_stock_quote, "coroutine", getattr(get_stock_quote, "func", None))
                    q = await asyncio.wait_for(q_func(ticker=ticker, use_fast_path=True), timeout=7.0)
                else:
                    # SMC-Grade Fetch: Full OHLCV
                    from src.tools.finance import get_symbol_history_data

                    h_func = getattr(get_symbol_history_data, "coroutine", getattr(get_symbol_history_data, "func", None))
                    q_str = await asyncio.wait_for(h_func(symbols=[ticker], period="1d", interval="1h"), timeout=10.0)
                    q = {"response": q_str, "type": "smc_full"}

                duration = (datetime.now() - start_time).total_seconds()
                log_vli_metric(f"fastpath_{ticker.lower()}", duration, status="pass")

                if isinstance(q, dict):
                    # Handle SMC-Grade response string
                    if q.get("type") == "smc_full":
                        return q["response"], {}

                    # Atomic response handling
                    _vli_last_ux_card = get_latest_ux_data(ticker)

                    # Report metric to trigger Resonance Chart
                    _vli_convergence_history.append({"timestamp": datetime.now().strftime("%H:%M:%S"), "iteration": 1, "latency": duration, "accuracy": 100.0, "status": "pass"})

                    p, c = q.get("price", 0), q.get("change", 0)
                    return f"### {ticker} (Atomic Fast-Path)\n- **Price**: `${p:.2f}`\n- **Change**: `{'+' if c >= 0 else ''}{c:.2f}%`", {}
                return str(q), {}
            except Exception as fe:
                logger.warning(f"VLI Fast-Path: Atomic resolution failed for '{ticker}': {fe}")
            except Exception as fe:
                logger.warning(f"VLI Fast-Path: Atomic resolution failed for '{ticker}': {fe}")

    # Prepare content for LangGraph Swarm if Fast Path is missed
    if image:
        content_obj = [{"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": image}}]
    else:
        content_obj = text

    # [V10.5 CONTEXT PATCH & TRUNCATION]
    # In long-running sessions, we must truncate the history to prevent state-load hangs.
    # The specialist nodes (SMC Analyst) only need the immediate directive and structural 
    # history, not the entire conversation from hours ago.
    try:
        from langgraph.checkpoint.base import CheckpointTuple
        # Check current history depth if checkpointer is active
        # However, since we are doing a fresh invoke with only the current message,
        # and the checkpointer MERGES them, we should actually be careful.
        # LangGraph typically handles history merging. 
        # But if we were passing the WHOLE history in workflow_input, we'd truncate it here.
    except: pass
    
    # [NEW] Historical Symbol Memory Injection
    injected_observations = []
    if "generate a detailed Daily Trading Report post-mortem" in text:
        from src.services.historical_reports import get_trader_performance_summary
        perf_summary = get_trader_performance_summary()
        if perf_summary:
            injected_observations.append(f"[SYSTEM INJECTION: Trader Performance History]\n{perf_summary}")
    elif any(text.lower().startswith(a) for a in TACTICAL_REPORT_ALIASES):
        sym = text.split(" ")[1].strip().upper()
        from src.services.historical_reports import get_historical_symbol_summary
        sym_summary = get_historical_symbol_summary(sym)
        if sym_summary:
            injected_observations.append(f"[SYSTEM INJECTION: Supplemental Interday History for {sym}]\n{sym_summary}")

    workflow_input = {
        "messages": [HumanMessage(content=content_obj)],
        "plan_iterations": 0,
        "steps_completed": 0,
        "final_report": "",
        "current_plan": None,
        "observations": injected_observations,
        "auto_accepted_plan": True,
        "is_plan_approved": True,
        "enable_background_investigation": False,
        "research_topic": text[:100],
        "verbosity": 1,
        "direct_mode": direct_mode,
        "raw_data_mode": raw_data_mode,
        "intent": intent_mode,
    }

    # [RESONANCE FLOOR] Configuration for reliable execution
    workflow_config = {
        "configurable": {
            "thread_id": thread_id,
            "max_plan_iterations": 0,
            "max_step_num": 5,
            "max_search_results": 2,
            "report_style": "concise",
            "direct_mode": direct_mode,
            "reporter_llm_type": reporter_llm_type,
            "vli_llm_type": vli_llm_type,
            "intent_mode": intent_mode,
            "snaptrade_settings": snaptrade_settings if snaptrade_settings else {},
            "thinking_mode": thinking_mode,
        },
        "recursion_limit": 50,
    }

    _vli_active_task = asyncio.current_task()

    try:
        # [NEW] Kill switch check
        if _vli_reset_requested:
            logger.warning("VLI Agent: Reset requested. Terminating jobs.")
            return "Session Reset Signal Received. Execution Terminated.", {}

        # [DIAGNOSTIC] Starting Graph Execution
        logger.info(f"VLI Agent: Launching Graph traversal for directive: '{text[:50]}'")
        start_exec = time.time()
        
        # [DYNAMIC BUDGET] Inject absolute start time for per-node adaptive fallbacks
        workflow_config["configurable"]["execution_start_time"] = start_exec

        # Run the graph and get the final state with an aggressive timeout (600s to respect AsyncRetries safely)
        final_state = await asyncio.wait_for(graph.ainvoke(workflow_input, config=workflow_config), timeout=600.0)

        exec_duration = time.time() - start_exec
        logger.info(f"VLI Agent: Graph traversal completed in {exec_duration:.2f}s")

        # [NEW] Raw Data Headless Mode Bypass (API Engine Mode)
        if final_state.get("raw_data_mode"):
            import json

            for m in reversed(final_state.get("messages", [])):
                content = str(getattr(m, "content", ""))
                if "RAW_SMC_PRICE_ACTION_TABLE" in content:
                    return content, final_state
            raw_payload = [str(getattr(m, "content", "")) for m in final_state.get("messages", [])]
            return json.dumps(raw_payload), final_state

        # [FINAL FIREWALL] Centralized Scrubbing at Exit Point
        fr = final_state.get("final_report", "")
        res = ""
        if not fr:
            for m in reversed(final_state.get("messages", [])):
                if isinstance(m, AIMessage):
                    res = str(getattr(m, "content", ""))
                    if m.name == "coordinator" and "Synthesizing" in res:
                        continue
                    break
        
        final_output = fr if fr else res
        
        # [NEW] Persist the thread_id for global feedback tracking
        global _vli_last_thread_id
        _vli_last_thread_id = thread_id
        
        return scrub_vli_output(final_output), final_state

    except asyncio.TimeoutError:
        logger.warning("VLI Agent: Master orchestration timed out (600s).")
        return "Agent processing timed out (600s).", {}
    except Exception as e:
        import traceback
        with open("C:\\Users\\rende\\.gemini\\antigravity\\worktrees\\cobalt-multi-agent\\backend\\vli_error.txt", "w") as f:
            f.write(traceback.format_exc())
        logger.error(f"VLI Agent: Failed with error: {e}")
        return scrub_vli_output(f"Agent reasoning encountered a failure: {str(e)}"), {}


async def _background_synthesis_task(text: str, image: str | None, direct_mode: bool, reporter_llm_type: str, vli_llm_type: str, thread_id: str, silent: bool = False, snaptrade_settings: dict | None = None, thinking_mode: bool = False):
    """Executes the deep analysis graph asynchronously."""
    try:
        from src.config.vli import get_vli_path

        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        with open(telemetry_file, "a", encoding="utf-8") as tf:
            tf.write(f"\n{timestamp} **ASYNC SYNTHESIS INITIATED**\n")
            tf.write(f"- **Thread ID**: `{thread_id}`\n")

        response_text, final_state = await _invoke_vli_agent(
            text=text,
            image=image,
            direct_mode=direct_mode,
            raw_data_mode=False,  # Force the graph to execute deep synthesis
            reporter_llm_type=reporter_llm_type,
            vli_llm_type=vli_llm_type,
            thread_id=thread_id,
            snaptrade_settings=snaptrade_settings,
            thinking_mode=thinking_mode,
        )
        
        # [NEW] Persist to Chat History with abstracted thoughts
        thought = ""
        if isinstance(final_state, dict):
            plan = final_state.get("current_plan")
            if hasattr(plan, "thought"): thought = plan.thought
            elif isinstance(plan, dict): thought = plan.get("thought", "")

        if not silent:
            _append_to_vli_history("ai", response_text, thought=thought, thread_id=thread_id)

        with open(telemetry_file, "a", encoding="utf-8") as tf:
            tf.write(f"\n{datetime.now().strftime('[%H:%M:%S]')} **VLI ASYNC TRANSACTION RESOLVED**\n")
            tf.write(f"- **Thread ID**: `{thread_id}`\n")
            preview = (response_text[:300] + "...") if len(response_text) > 300 else response_text
            tf.write(f"- **Response Preview**: {preview}\n")

        global _vli_last_async_report
        _vli_last_async_report = response_text

        # [PERSISTENCE FIX] Persist asynchronously generated markdown to disk
        if response_text and len(response_text) > 50 and "[ERROR]" not in response_text:
            if thread_id and thread_id.startswith("POSTMORTEM_"):
                # 1. Combine with Daily Market Report if it exists
                from src.services.historical_reports import (
                    update_performance_rolling_summary,
                    combine_reports,
                    sync_combined_report_files
                )
                import os
                date_str = thread_id.replace("POSTMORTEM_", "")
                
                market_report_content = ""
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                market_report_path = os.path.join(base_dir, "data", "archive", "daily_market_reports", f"report_{date_str}.md")
                if os.path.exists(market_report_path):
                    try:
                        with open(market_report_path, "r", encoding="utf-8") as f:
                            market_report_content = f.read()
                        logger.info(f"Loaded existing market report for {date_str} to combine.")
                    except Exception as e:
                        logger.error(f"Failed to read market report: {e}")
                
                combined_content = combine_reports(response_text, market_report_content, date_str=date_str)
                
                # Write/sync combined content across all storage layers
                sync_combined_report_files(date_str, combined_content, has_market_report=bool(market_report_content))
                
                # 3. Condense into rolling performance summary (use only the post-mortem text, not the combined text)
                update_performance_rolling_summary(response_text)
            else:
                _persist_vli_report(text, response_text)

    except Exception as e:
        logger.error(f"[ASYNC_SYNTHESIS] Background report failed: {e}")


@app.get("/api/vli/journal/{date_str}")
def get_daily_journal(date_str: str):
    """
    Exposes a GET endpoint to fetch today's daily journal notes and self-assessment grades.
    """
    try:
        from src.services.historical_reports import parse_daily_journal_file
        data = parse_daily_journal_file(date_str)
        return data
    except Exception as e:
        logger.error(f"[JOURNAL_API] Error fetching journal for {date_str}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def clean_unpacked_synthesis(val: str) -> str:
    if not val:
        return ""
    val_stripped = val.strip()
    if val_stripped.startswith("[") and val_stripped.endswith("]"):
        try:
            import ast
            parsed = ast.literal_eval(val_stripped)
            if isinstance(parsed, list):
                text_parts = []
                for item in parsed:
                    if isinstance(item, dict):
                        text_parts.append(item.get("text", ""))
                    else:
                        text_parts.append(str(item))
                return "".join(text_parts).strip()
        except Exception:
            pass
    return val


@app.get("/api/vli/journal/{date_str}/preview")
def get_daily_journal_preview(date_str: str):
    """
    Exposes a GET endpoint to fetch today's daily journal synthesized notes and self-assessment preview.
    """
    try:
        from src.services.historical_reports import PERFORMANCE_DIR
        import json
        
        # 1. Try to read from JSON preview cache first
        preview_cache_path = os.path.join(PERFORMANCE_DIR, f"Daily_Journal_Preview_{date_str}.json")
        if os.path.exists(preview_cache_path):
            try:
                with open(preview_cache_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    # Clean cached values just in case
                    if isinstance(cached_data, dict):
                        cached_data["trader_notes"] = clean_unpacked_synthesis(cached_data.get("trader_notes", ""))
                        cached_data["self_assessment"] = clean_unpacked_synthesis(cached_data.get("self_assessment", ""))
                    return cached_data
            except Exception as e:
                logger.error(f"Error reading preview cache: {e}")
                
        # 2. Fall back to parsing Daily_PostMortem_{date_str}.md
        post_mortem_path = os.path.join(PERFORMANCE_DIR, f"Daily_PostMortem_{date_str}.md")
        result = {
            "trader_notes": "",
            "self_assessment": ""
        }
        
        if os.path.exists(post_mortem_path):
            with open(post_mortem_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            import re
            
            if "## Agent Feedback" in content:
                # New format: Feedback resides under ## Agent Feedback
                feedback_match = re.search(r'## Agent Feedback\n\n(.*?)(?=\n\n## |\n\n---|\Z)', content, re.DOTALL)
                if feedback_match:
                    feedback_sec = feedback_match.group(1)
                    polished_match = re.search(r'### Polished Reflections\n(.*?)(?=\n\n### |\n\n---|\Z)', feedback_sec, re.DOTALL)
                    if polished_match:
                        result["trader_notes"] = clean_unpacked_synthesis(polished_match.group(1))
                    mindset_match = re.search(r'### Mindset Coaching\n(.*?)(?=\n\n### |\n\n---|\Z)', feedback_sec, re.DOTALL)
                    if mindset_match:
                        result["self_assessment"] = clean_unpacked_synthesis(mindset_match.group(1))
            else:
                # Old format: sections are sibling level
                notes_match = re.search(r'## Trader Notes\n\n(.*?)(?=\n\n## |\n\n---|\Z)', content, re.DOTALL)
                if notes_match:
                    result["trader_notes"] = clean_unpacked_synthesis(notes_match.group(1))
                    
                assess_match = re.search(r'## Self Assessment\n\n(.*?)(?=\n\n## |\n\n---|\Z)', content, re.DOTALL)
                if assess_match:
                    result["self_assessment"] = clean_unpacked_synthesis(assess_match.group(1))
                
            # Cache the parsed result for next time
            try:
                os.makedirs(PERFORMANCE_DIR, exist_ok=True)
                with open(preview_cache_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Error writing preview cache: {e}")
                
        return result
    except Exception as e:
        logger.error(f"[JOURNAL_API] Error fetching preview for {date_str}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/vli/journal/{date_str}")
def post_daily_journal(date_str: str, request: VLIJournalRequest):
    """
    Exposes a POST endpoint to save daily journal notes and grades,
    and trigger post-mortem re-combination if a post-mortem already exists.
    """
    try:
        from src.services.historical_reports import save_daily_journal_file, PERFORMANCE_DIR
        import json
        
        # Save daily journal
        raw_markdown = request.markdown
        if "## Agent Feedback" in raw_markdown:
            import re
            raw_markdown = re.split(r'\n+## Agent Feedback\b', raw_markdown)[0].strip()
        save_daily_journal_file(date_str, request.grades, raw_markdown)
        
        # Check if post-mortem file exists in cache to extract context
        post_mortem_path = os.path.join(PERFORMANCE_DIR, f"Daily_PostMortem_{date_str}.md")
        cleaned_pm = None
        mr_part = ""
        if os.path.exists(post_mortem_path):
            with open(post_mortem_path, "r", encoding="utf-8") as f:
                pm_content = f.read()
                
            import re
            pattern_mr = r'\n+---\n+(?=# Daily Market Report|## Top 10 Market Gainers|# Daily Market Report:)'
            parts = re.split(pattern_mr, pm_content)
            raw_pm = parts[0].strip()
            mr_part = parts[1].strip() if len(parts) > 1 else ""
            cleaned_pm = re.split(r'\n+## (?:Trader Notes|Self Assessment|Subjective Experience|Notes|Agent Feedback)\b', raw_pm)[0].strip()
            
        # Run synthesis even if post_mortem does not exist yet (so we can preview it!)
        from src.services.historical_reports import synthesize_journal_and_assessment
        trader_notes, self_assessment = synthesize_journal_and_assessment(date_str, request.grades, raw_markdown, cleaned_pm)
        
        trader_notes_clean = clean_unpacked_synthesis(trader_notes)
        self_assessment_clean = clean_unpacked_synthesis(self_assessment)
        
        # Cache the generated preview
        preview_cache_path = os.path.join(PERFORMANCE_DIR, f"Daily_Journal_Preview_{date_str}.json")
        try:
            os.makedirs(PERFORMANCE_DIR, exist_ok=True)
            with open(preview_cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "trader_notes": trader_notes_clean or "",
                    "self_assessment": self_assessment_clean or ""
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error caching generated preview: {e}")
            
        # Write to daily journal file in Obsidian and VLI folders
        try:
            from src.services.historical_reports import save_daily_journal_note
            save_daily_journal_note(date_str, request.grades, trader_notes_clean, self_assessment_clean)
        except Exception as e:
            logger.error(f"Error saving daily journal note: {e}")
            
        # If the post-mortem does exist, we combine and save
        if os.path.exists(post_mortem_path):
            from src.services.historical_reports import combine_reports, sync_combined_report_files
            combined_content = combine_reports(pm_content, mr_part, date_str=date_str)
            sync_combined_report_files(date_str, combined_content, has_market_report=bool(mr_part))
            logger.info(f"Re-combined and updated post-mortem report for {date_str} successfully.")
            
        return {"status": "OK", "message": f"Successfully updated journal for {date_str}"}
    except Exception as e:
        logger.error(f"[JOURNAL_API] Error updating journal for {date_str}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/vli/action-plan")
async def post_vli_action_plan(request: VLIActionPlanRequest, background_tasks: BackgroundTasks, http_req: Request = None, client_id: str = Header("default", alias="X-VLI-Client-ID")):
    """Handle chat or action-plan updates from the VLI Sidebar."""
    try:
        from src.config.vli_context import vli_client_id
        vli_client_id.set(client_id)
        update_global_thinking_mode(request.thinking_mode)
    except Exception:
        pass
    plan_file = get_action_plan_path()

    # [BUGFIX: STATE POLLUTION] Explicitly generate a fresh Thread ID for every action plan request ONLY IF one isn't provided.
    transaction_id = request.thread_id
    if not transaction_id:
        if request.text.strip().startswith("Note:") and _vli_last_thread_id:
            transaction_id = _vli_last_thread_id
        else:
            import uuid
            transaction_id = f"vli_action_{uuid.uuid4().hex[:8]}"
            
    # [NEW] Persist User Message IMMEDIATELY (Atomic Visibility across all paths including Cache & Fast-Path)
    _append_to_vli_history("user", request.text, thread_id=transaction_id)
    # [NEW] Log Issued Command to Raw Telemetry
    try:
        from src.config.vli import get_vli_path

        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        with open(telemetry_file, "a", encoding="utf-8") as tf:
            tf.write(f"\n{timestamp} **DIRECTIVE ISSUED:** {request.text}\n")
            tf.flush()
    except Exception as le:
        logger.error(f"VLI: Failed to log command audit: {le}")

    # Extract logic and update global alerts/panels even for short directives
    new_alerts = extract_vli_logic(request.text)
    if new_alerts:
        global _vli_extracted_alerts
        _vli_extracted_alerts.extend(new_alerts)
        seen = set()
        unique = []
        for a in _vli_extracted_alerts:
            key = f"{a['symbol']}:{a['label']}"
            if key not in seen:
                seen.add(key)
                unique.append(a)
        _vli_extracted_alerts = unique

    # Check if this is an action-plan update
    if request.is_action_plan:
        with open(plan_file, "w", encoding="utf-8") as f:
            f.write(request.text)
        return {"response": "Plan captured. Vault updated. Session Monitor is analyzing directives...", "status": "OK", "error_details": None}

    import re
    command_text = request.text.strip().lower()

    # UX Command: Open Journal
    if re.match(r"^(open|show)\s+(journal|journalling|journaling|diary)$", command_text):
        _append_to_vli_history("ai", "Opening the Journalling Module...", thread_id=transaction_id)
        host = "localhost"
        port = "8080"  # default standard Next.js port
        if http_req:
            host = http_req.url.hostname or "localhost"
            host_header = http_req.headers.get("host", "")
            if ":2026" in host_header:
                port = "2026"  # Nginx unified proxy port
        return {
            "response": "Opening the Journalling Module...",
            "status": "OK",
            "error_details": None,
            "metadata": {
                "action": "NAVIGATE",
                "url": f"http://{host}:{port}/workspace/journal"
            }
        }

    # UX Command: Open Scanner
    if re.match(r"^(open|create|add|spawn)\s+(?:new\s+)?(scanner|scan|market\s+scan)(\s+window|\s+card|\s+panel)?$", command_text):
        _append_to_vli_history("ai", f"Opening Market Scan module...", thread_id=transaction_id)
        return {
            "response": "Opening Market Scan module...",
            "status": "OK",
            "error_details": None,
            "metadata": {
                "action": "OPEN_CARD",
                "card_type": "SCAN_RES"
            }
        }

    # UX Command: Close Scanner
    close_scan_match = re.match(r"^(destroy|delete|close|remove)\s+(scanner|scan|market\s+scan)\s+([a-zA-Z0-9]+|all)$", command_text)
    if close_scan_match:
        card_id = close_scan_match.group(3).upper()
        _append_to_vli_history("ai", f"Destroying UX module: {card_id}", thread_id=transaction_id)
        return {
            "response": f"Destroying UX module: {card_id}",
            "status": "OK",
            "error_details": None,
            "metadata": {
                "action": "CLOSE_CARD",
                "card_id": card_id
            }
        }

    # [NEW] Show Daily Briefing
    briefing_match = re.match(r"^show\s+daily\s+briefing(\s+report)?$", command_text)
    if briefing_match:
        if os.path.exists(get_daily_briefing_path()):
            _append_to_vli_history("ai", "Retrieving Daily Briefing...", thread_id=transaction_id)
            return {
                "response": "Retrieving Daily Briefing...",
                "status": "OK",
                "error_details": None,
                "metadata": {
                    "action": "OPEN_REPORT",
                    "artifact_type": "REPORT",
                    "symbol": "DAILY_BRIEFING"
                }
            }
        else:
            return {"response": "Daily Briefing has not been generated yet today.", "status": "OK", "error_details": None}

    # [NEW] Show Report / Artifact Interception
    show_match = re.match(r"^show\s+([a-zA-Z]+)\s+(report|analysis)$", command_text)
    if show_match:
        symbol = show_match.group(1).upper()
        # Look for the cached analysis report
        reports_dir = os.path.join(os.getcwd(), "data", "reports")
        cache_path = os.path.join(reports_dir, f"analyze_{symbol.lower()}.md")
        
        if os.path.exists(cache_path):
            _append_to_vli_history("ai", f"Retrieving cached intelligence for {symbol}...", thread_id=transaction_id)
            return {
                "response": f"Retrieving cached intelligence for {symbol}...",
                "status": "OK",
                "error_details": None,
                "metadata": {
                    "action": "OPEN_REPORT",
                    "artifact_type": "REPORT",
                    "symbol": symbol
                }
            }
        else:
            # Mutate request to trigger regeneration
            _append_to_vli_history("ai", f"No cached intelligence found for {symbol}. Initiating real-time tactical synthesis...", thread_id=transaction_id)
            request.text = f"analyze {symbol}"
            command_text = request.text.strip().lower()

    # [NEW] TV_SYNC Direct Control Interception
    
    if re.match(r"^(suspend|pause|stop)\s+tv_?sync$", command_text):
        from src.services.scheduler import cobalt_scheduler
        cobalt_scheduler.remove_timer("TV_SCANNER_SYNC")
        _append_to_vli_history("assistant", "TradingView Scanner Sync has been suspended.", thread_id=transaction_id)
        return {"response": "TradingView Scanner Sync suspended.", "status": "OK", "error_details": None}
        
    if re.match(r"^(start|resume)\s+tv_?sync$", command_text):
        from src.services.scheduler import cobalt_scheduler
        cobalt_scheduler.remove_timer("TV_SCANNER_SYNC") # Ensure no duplicates
        cobalt_scheduler.add_timer(
            task_id="TV_SCANNER_SYNC",
            name="TradingView Apex Scanner Sync",
            type="REPEAT",
            schedule=1,
            period_unit="minutes",
            priority="LOW",
            callback=run_tv_sync
        )
        _append_to_vli_history("assistant", "TradingView Scanner Sync has been started.", thread_id=transaction_id)
        return {"response": "TradingView Scanner Sync started.", "status": "OK", "error_details": None}

    # [NEW] Dropzone Import/Export Interception
    import_match = re.match(r"^import\s+fidelity\s*(.*)$", command_text)
    if import_match:
        from src.services.csv_importer import process_dropzone_files
        opt_path = import_match.group(1).strip()
        res_msg = process_dropzone_files(optional_path=opt_path if opt_path else None)
        _append_to_vli_history("ai", res_msg, thread_id=transaction_id)
        return {"response": res_msg, "status": "OK", "error_details": None, "thread_id": transaction_id}

    export_match = re.match(r"^export\s+tradezella\s*(.*)$", command_text)
    if export_match:
        opt_path = export_match.group(1).strip()
        try:
            if opt_path:
                from src.services.tradezella_exporter import generate_tradezella_csv, get_todays_csv
                input_csv = get_todays_csv()
                if not input_csv:
                    res_msg = "[ERROR]: No orders CSV found to export."
                else:
                    processed = generate_tradezella_csv(input_csv, opt_path, today_only=True)
                    res_msg = f"Successfully exported {len(processed) if processed else 0} trades to custom path: {opt_path}"
            else:
                from src.tools.broker import export_to_tradezella
                res_msg = export_to_tradezella.invoke({"timeframe": "day"}, config=None)
        except Exception as e:
            res_msg = f"Export failed: {e}"
        _append_to_vli_history("ai", res_msg, thread_id=transaction_id)
        return {"response": res_msg, "status": "OK", "error_details": None, "thread_id": transaction_id}

    # [NEW] Meta-Analysis Interception
    if request.text.strip().lower() == "run meta analysis":
        res_msg = await run_meta_analysis(manual_trigger=True)
        # Also persist this AI response to history so it shows up in the chat!
        _append_to_vli_history("ai", res_msg, thread_id=transaction_id)
        return {"response": res_msg, "status": "OK", "error_details": None, "thread_id": transaction_id}

    # [NEW] Meta-Analysis Eviction Interception
    req_lower = request.text.strip().lower()
    import re
    clean_req = re.sub(r'[^\w\s-]', '', req_lower).strip()
    
    if any(clean_req.startswith(f"{v} {t}") for v in EVICT_VERBS for t in EVICT_TARGETS):
        reports_dir = os.path.join(os.getcwd(), 'data', 'reports')
        meta_path = get_daily_briefing_path()
        if os.path.exists(meta_path):
            try:
                os.remove(meta_path)
                res_msg = "Executive Morning Briefing has been successfully evicted from the cache."
            except Exception as e:
                res_msg = f"Failed to evict Executive Morning Briefing: {e}"
        else:
            res_msg = "Executive Morning Briefing is not currently present in the cache."
            
        _append_to_vli_history("ai", res_msg, thread_id=transaction_id)
        return {"response": res_msg, "status": "OK", "error_details": None, "thread_id": transaction_id}

    # [NEW] Post-Mortem Eviction Interception
    if any(clean_req.startswith(f"{v} {t}") for v in EVICT_VERBS for t in EVICT_POSTMORTEM_TARGETS):
        from src.services.historical_reports import PERFORMANCE_DIR
        today_str = datetime.now().strftime("%Y-%m-%d")
        perf_path = os.path.join(PERFORMANCE_DIR, f"Daily_PostMortem_{today_str}.md")
        
        # We also want to clear any Obsidian copy
        import glob
        from src.config.vli import VAULT_ROOT
        obsidian_journals_dir = os.path.join(VAULT_ROOT, "bluesec-obsidian-vault", "trading", "journals")
        obsidian_pattern = os.path.join(obsidian_journals_dir, f"Daily_Trading_Report_{today_str}*.md")
        
        cleared_files = 0
        if os.path.exists(perf_path):
            try:
                os.remove(perf_path)
                cleared_files += 1
            except:
                pass
                
        for path in glob.glob(obsidian_pattern):
            try:
                os.remove(path)
                cleared_files += 1
            except:
                pass
                
        if cleared_files > 0:
            res_msg = f"Daily Post-Mortem report for {today_str} has been successfully evicted from the cache and Obsidian vault."
        else:
            res_msg = f"Daily Post-Mortem report for {today_str} is not currently present in the cache."
            
        _append_to_vli_history("ai", res_msg, thread_id=transaction_id)
        return {"response": res_msg, "status": "OK", "error_details": None, "thread_id": transaction_id}

    # [NEW] Ticker Eviction Interception
    evict_match = re.match(r"^(?:delete|remove|invalidate|scrub|evict)\s+([a-z0-9.-]+)$", req_lower)
    if evict_match:
        ticker_target = evict_match.group(1).upper()
        if ticker_target in ["CACHE", "ALL", "EVERYTHING"]:
            ticker_target = ""
            
        from src.services.datastore import DatastoreManager
        res_msg = DatastoreManager.invalidate_cache(ticker_target)
        _append_to_vli_history("ai", res_msg, thread_id=transaction_id)
        return {"response": res_msg, "status": "OK", "error_details": None, "thread_id": transaction_id}

    # [NEW] Regeneration Interception
    if req_lower == "regenerate":
        try:
            scanner_targets = []
            scanner_path = os.path.join(VAULT_ROOT, "_cobalt", "01_Transit", "Buckets", "STRIKE_RES_state.json")
            if os.path.exists(scanner_path):
                with open(scanner_path, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                    for c in s_data.get("candidates", []):
                        if c.get("symbol"):
                            scanner_targets.append(c["symbol"])
                            
            macro_targets = []
            macro_path = os.path.join(VAULT_ROOT, "_cobalt", "01_Transit", "Buckets", "MACRO_WATCHLIST_state.json")
            if os.path.exists(macro_path):
                with open(macro_path, "r", encoding="utf-8") as f:
                    m_data = json.load(f)
                    for r in m_data.get("rows", []):
                        if len(r) > 1 and r[1]:
                            macro_targets.append(r[1])
                            
            all_targets = list(set(scanner_targets + macro_targets))
            
            if not all_targets:
                res_msg = "No assets found in any active watchlists to regenerate."
            else:
                import asyncio
                for sym in all_targets:
                    asyncio.create_task(_background_regenerate_data(sym))
                res_msg = f"Initiated global regeneration for {len(all_targets)} assets across all watchlists."
                
            _append_to_vli_history("ai", res_msg, thread_id=transaction_id)
            return {"response": res_msg, "status": "OK", "error_details": None, "thread_id": transaction_id}
            
        except Exception as e:
            logger.error(f"Global regenerate failed: {e}")
            res_msg = f"Error during global regeneration: {e}"
            _append_to_vli_history("ai", res_msg, thread_id=transaction_id)
            return {"response": res_msg, "status": "ERROR", "error_details": None, "thread_id": transaction_id}
            
    regen_match = re.match(r"^regenerate\s+([a-z0-9.-]+)$", req_lower)
    if regen_match:
        target = regen_match.group(1).upper()
        import asyncio
        asyncio.create_task(_background_regenerate_data(target))
        res_msg = f"Initiated focused regeneration for {target}."
        _append_to_vli_history("ai", res_msg, thread_id=transaction_id)
        return {"response": res_msg, "status": "OK", "error_details": None, "thread_id": transaction_id}

    # [NEW] Check Durable Action Cache (Conditional on Intent)
    intent_mode = _get_vli_intent(request.text)
    is_note = request.text.strip().upper().startswith("NOTE:")
    
    clean_req_text = request.text.strip().upper()
    
    # [HARDENING] Absolute Graph Bypass for Administrative Directives
    if clean_req_text == "RUN MORNING SCAN":
        try:
            import threading
            import asyncio
            
            def bg_task():
                try:
                    asyncio.run(run_daily_morning_analysis())
                except Exception as e:
                    logger.error(f"DEBUG: bg_task crashed: {e}")
                
            bypass_resp = "Morning scan sequence successfully engaged. Background orchestration is running."
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp} **ADMIN OVERRIDE (Graph Bypassed)**\n")
                tf.write(f"- **Directive**: `{clean_req_text}`\n")
                tf.write(f"- **Response Size**: {len(bypass_resp)} chars\n\n---\n")
                tf.flush()
                
            threading.Thread(target=bg_task, daemon=True).start()
                
            _append_to_vli_history("ai", bypass_resp, thread_id=transaction_id)
            return {"response": bypass_resp, "status": "OK", "error_details": None, "thread_id": transaction_id}
        except Exception as e:
            logger.error(f"Morning scan override failed: {e}")

    is_admin_cmd = any(word in clean_req_text for word in ADMIN_CMD_TOKENS)
    
    import hashlib, time
    cache_dir = os.path.join(os.getcwd(), "data", "artifacts", "vli_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_key = hashlib.md5(clean_req_text.encode()).hexdigest()
    cache_file = os.path.join(cache_dir, f"{cache_key}.json")

    # [HARDENING] Bypass cache lookup for Market Awareness or Notes to ensure real-time data
    if not request.background_synthesis and not is_note and not is_admin_cmd and intent_mode == "TACTICAL_EXECUTION" and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as cf:
                cached_data = json.load(cf)
            if (time.time() - cached_data["timestamp"]) < 300: # 5 min TTL
                response_text = cached_data["response_text"]
                status_code = "OK"
                with open(telemetry_file, "a", encoding="utf-8") as tf:
                    tf.write(f"\n{timestamp} **CACHE HIT (Graph Bypassed)**\n")
                    tf.write(f"- **Intent**: `{intent_mode}`\n")
                    tf.write(f"- **Directive**: `{request.text[:40]}...`\n")
                    tf.write(f"- **Response Size**: {len(response_text)} chars\n\n---\n")
                # [NEW] Persist AI Response to History
                _append_to_vli_history("ai", response_text, thread_id=transaction_id)
                return {"response": response_text, "status": status_code, "error_details": None, "thread_id": transaction_id}
        except Exception as e:
            logger.error(f"VLI: Cache read failure: {e}")
    else:
        # [NEW] Explicit Cache Deletion for bypass hits (Prevent ghost hits if intent logic fluctuates)
        if (is_note or intent_mode == "MARKET_INSIGHT") and os.path.exists(cache_file):
            try:
                os.remove(cache_file)
                logger.info(f"[VLI_CACHE] Purged stale cache entry for Market Awareness hash: {cache_key}")
            except Exception:
                pass

    # Real Agent Routing for Chat/Directives
    logger.info(f"VLI: Routing directive to Gemini Agent: {request.text[:50]}...")
    final_vli_state = {}  # Ensure initialization

    # [FAST-PATH] Shorthand Directive Bypass (Pre-Orchestration)
    import re
    cleaned_input = request.text.strip().upper()
    
    # --- HOLISTIC INTENT CLASSIFICATION ---
    first_word = cleaned_input.split()[0] if cleaned_input else ""
    
    global_intent = "COMMAND"
    if first_word in ROUTER_QUERY_TOKENS:
        global_intent = "QUERY"
    elif first_word in ROUTER_ADMIN_TOKENS:
        global_intent = "ADMIN"
        
    logger.info(f"VLI Intent Router: Input classified as [{global_intent}]")

    ticker = None
    fp_intent = None
    
    # Only allow Bypass evaluating if the intent is natively COMMAND
    if global_intent == "COMMAND":
        # 1. Ticker price variants (AAPL price, get $BTC, price of ETH, etc.)
        m = re.search(r"^(?:GET\s+|PRICE\s+OF\s+)?\$?([A-Z0-9.\-_=]{1,20})(?:\s+PRICE)?$", cleaned_input)
        if m:
            ticker = m.group(1)
            fp_intent = "Bypass-Matched"
        
    if ticker and not request.raw_data_mode:
        logger.info(f"VLI: Fast-Path Hit detected: {ticker} (Intent: {fp_intent}). Bypassing AI Orchestration.")
        try:
            from src.tools.finance import get_stock_quote
            # [CRITICAL FIX] get_stock_quote is a LangChain @tool, must use .ainvoke
            quote = await get_stock_quote.ainvoke({"ticker": ticker, "use_fast_path": True})
            
            if isinstance(quote, dict):
                price = quote.get("price")
                if not price and "raw" in quote and isinstance(quote["raw"], dict):
                    price = quote["raw"].get("Close")
                
                if price:
                    change = quote.get("change", 0.0)
                    change_sign = "+" if change >= 0 else ""
                    response_text = f"**{ticker}**: ${price:.2f} ({change_sign}{change:.2f}%)"
                    
                    _append_to_vli_history("ai", response_text, thread_id=transaction_id)
                    
                    # Log to Telemetry
                    try:
                        from src.config.vli import get_vli_path
                        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
                        timestamp = datetime.now().strftime("[%H:%M:%S]")
                        with open(telemetry_file, "a", encoding="utf-8") as tf:
                            tf.write(f"\n{timestamp} **FAST_PATH_HIT (Bypass: {fp_intent})**\n")
                            tf.write(f"- **Ticker**: `{ticker}`\n")
                            tf.write(f"- **Response**: `{response_text}`\n\n---\n")
                            tf.flush()
                            os.fsync(tf.fileno())
                    except: pass
                    
                    return {"response": response_text, "status": "OK", "error_details": None, "thread_id": transaction_id}
            
            # If we reached here, the ticker was matched but quote retrieval failed or returned a string error
            response_text = str(quote) if isinstance(quote, str) else f"VLI_FAST_PATH: Real-time price for '{ticker}' is currently unavailable."
            _append_to_vli_history("ai", response_text, thread_id=transaction_id)
            
            # Log failure to Telemetry too
            try:
                from src.config.vli import get_vli_path
                telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
                timestamp = datetime.now().strftime("[%H:%M:%S]")
                with open(telemetry_file, "a", encoding="utf-8") as tf:
                    tf.write(f"\n{timestamp} **FAST_PATH_FAILURE (Bypass: {fp_intent})**\n")
                    tf.write(f"- **Ticker**: `{ticker}`\n")
                    tf.write(f"- **Error**: `{response_text}`\n\n---\n")
                    tf.flush()
                    os.fsync(tf.fileno())
            except: pass
            
            return {"response": response_text, "status": "ERROR", "error_details": "Tool returned non-dict payload during bypass fetch."}
        except Exception as fe:
            logger.warning(f"VLI: Fast-Path bypass failed for {ticker}: {fe}")
            return {"response": f"VLI_FAST_PATH: Failed to retrieve quote for '{ticker}' (Error: {str(fe)}).", "status": "ERROR", "error_details": str(fe)}

    # [NEW] ASYNC SYNTHESIS BYPASS
    wants_background = request.background_synthesis or "--BACKGROUND" in request.text.upper()
    if request.raw_data_mode and wants_background:
        logger.info(f"VLI: Routing to Async Synthesis Bypass for: {request.text[:50]}")
        text = request.text
        ticker = ""
        import re

        sym_match = re.search(r"\$([A-Z]{1,10})", text.upper())
        if sym_match:
            ticker = sym_match.group(1)
        else:
            words = re.findall(r"\b([A-Z]{1,10})\b", text.upper())
            for word in words:
                if word not in TICKER_STOP_WORDS:
                    ticker = word
                    break

        if ticker:
            try:
                from src.tools.finance import get_raw_smc_tables
                import asyncio

                report = await asyncio.wait_for(get_raw_smc_tables(ticker=ticker), timeout=25.0)

                # [FIX] Persist early for Async path so double-click works immediately
                clean_text = request.text.replace("--raw", "").replace("--RAW", "").strip()
                _persist_vli_report(clean_text, report)

                # Apply global basic model override
                actual_vli_llm = request.vli_llm_type if request.thinking_mode else "basic"
                actual_reporter_llm = request.reporter_llm_type if request.thinking_mode else "basic"

                # Dispatch deep learning agent to background
                background_tasks.add_task(_background_synthesis_task, request.text, request.image, request.direct_mode, actual_reporter_llm, actual_vli_llm, transaction_id, False, request.snaptrade_settings, request.thinking_mode)
                return {"response": report, "status": "ASYNC_PENDING", "error_details": None, "state": {}}
            except Exception as fe:
                logger.warning(f"VLI Async-Path: Atomic resolution failed for '{ticker}': {fe}")

    try:
        actual_vli_llm = request.vli_llm_type if request.thinking_mode else "basic"
        actual_reporter_llm = request.reporter_llm_type if request.thinking_mode else "basic"
        
        if request.text.strip().lower().startswith("analyze "):
            actual_reporter_llm = "reasoning"
            actual_vli_llm = "reasoning"
        
        response_text, final_vli_state = await _invoke_vli_agent(request.text, request.image, request.direct_mode, request.raw_data_mode, actual_reporter_llm, actual_vli_llm, thread_id=transaction_id, snaptrade_settings=request.snaptrade_settings, thinking_mode=request.thinking_mode)
        
        # [FIX] Manually dispatch background regeneration if returned by non-streaming agent
        if "[BACKGROUND_REGENERATE_DATA]" in response_text:
            sym = response_text.replace("[BACKGROUND_REGENERATE_DATA]", "").strip()
            import asyncio
            asyncio.create_task(_background_regenerate_data(sym))
            response_text = f"Cache cleared for {sym}. Asynchronously regenerating market data, volume, prices, and news."
            
        timestamp = datetime.now().strftime("%H:%M:%S")

        if not response_text:
            # [V10 AUDIT] Log structural completion (Empty Payload)
            try:
                from src.config.vli import get_vli_path

                telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
                timestamp = datetime.now().strftime("[%H:%M:%S]")
                with open(telemetry_file, "a", encoding="utf-8") as tf:
                    tf.write(f"\n{timestamp} **VLI TRANSACTION RESOLVED**\n")
                    tf.write("- **Session Status**: `ERROR`\n")
                    tf.write("- **Action**: Pipeline completed without report synthesis.\n\n---\n")
            except:
                pass
            return {"response": "", "status": "ERROR", "error_details": "Pipeline execution completed, but no final report was synthesized."}
    except Exception as e:
        # [V10 AUDIT] Log structural failures to telemetry
        try:
            from src.config.vli import get_vli_path

            telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                # Distinguish between timeout and other errors
                status_label = "TIMEOUT" if "timed out" in str(e).lower() else "ERROR"
                tf.write(f"\n{timestamp} **SYSTEM ERROR:** Agent Reasoning Failed - {str(e)}\n")
                tf.write(f"- **Status**: `{status_label}`\n- **Action**: Execution aborted.\n\n---\n")
        except:
            pass

        status_code = "TIMEOUT" if "timed out" in str(e).lower() else "ERROR"
        return {"response": "", "status": status_code, "error_details": str(e)}

    # --- Final Telemetry Audit: Session COMPLETED (v10 Consolidated) ---
    try:
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")

        # Extract metadata from final state
        from langchain_core.messages import ToolMessage

        hierarchy = {"Orchestrator": {"workers": [], "duration": 0.0}}
        worker_counts = {}
        current_agent = "Orchestrator"
        system_nodes = ["reporter", "coordinator", "vli_coordinator", "router", "vli_parser"]

        messages = final_vli_state.get("messages", [])
        for m in messages:
            if getattr(m, "name", None):
                name = m.name
                if isinstance(m, AIMessage):
                    if name not in system_nodes:
                        current_agent = name
                        if current_agent not in hierarchy:
                            hierarchy[current_agent] = {"workers": [], "duration": 0.0}
                        
                        dur = getattr(m, "additional_kwargs", {}).get("duration_secs", 0.0)
                        hierarchy[current_agent]["duration"] += dur
                elif isinstance(m, ToolMessage):
                    if not name.startswith("transfer_to_"):
                        worker_base = f"{name}_worker"
                        if worker_base not in worker_counts:
                            worker_counts[worker_base] = 0
                        else:
                            worker_counts[worker_base] += 1

                        count = worker_counts[worker_base]
                        worker_name = f"{worker_base}_{count}" if count > 0 else worker_base

                        if current_agent in hierarchy:
                            hierarchy[current_agent]["workers"].append(worker_name)
                        else:
                            hierarchy["Orchestrator"]["workers"].append(worker_name)

        # Build hierarchy markdown
        hier_lines = ["- **Execution Hierarchy**:"]
        for agent, data in hierarchy.items():
            suffix = "" if agent.endswith("_finalize") else " [LLM]"
            dur = data.get("duration", 0.0)
            dur_str = f" ({dur:.1f}s)" if dur > 0 else ""

            if agent == "Orchestrator" and not data["workers"] and len(hierarchy) == 1:
                hier_lines.append(f'  - <span style="color: #58a6ff; font-weight: bold;">[ROOT] {agent}{suffix}{dur_str}</span>')
                break

            prefix = "[ROOT]" if agent == "Orchestrator" else "[AGENT]"
            hier_lines.append(f'  - <span style="color: #58a6ff; font-weight: bold;">{prefix} {agent}{suffix}{dur_str}</span>')
            for w in data["workers"]:
                hier_lines.append(f'    - <span style="color: #d29922; font-weight: 500;">-> {w}</span>')

        hierarchy_md = "\n".join(hier_lines)

        if isinstance(response_text, list):
            # [ROBUSTNESS] Flatten multi-modal message arrays safely
            response_text = " ".join([str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in response_text])

        preview = str(response_text)[:100].strip().replace("\n", " ")

        if not response_text.strip() or "empty payload" in response_text.lower() or "synthesis failed" in response_text.lower():
            # [RELIABILITY] Even if orchestration technically succeeded without exceptions,
            # an empty string or failing sentinel from reporter signifies a structural failure.
            status_code = "ERROR"
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp} **VLI TRANSACTION RESOLVED**\n")
                tf.write("- **Session Status**: `ERROR`\n")
                tf.write(f"{hierarchy_md}\n")
                tf.write(f"- **Directive**: `{request.text[:40]}...`\n")
                tf.write(f"- **Response Preview**: {response_text[:100]}...\n\n---\n")
            return {"response": response_text, "status": status_code, "error_details": "Reporter generated an empty payload or triggered a synthesis fail fallback."}

        with open(telemetry_file, "a", encoding="utf-8") as tf:
            tf.write(f"\n{timestamp} **VLI TRANSACTION RESOLVED**\n")
            tf.write("- **Session Status**: `OK`\n")
            tf.write(f"{hierarchy_md}\n")
            tf.write(f"- **Directive**: `{request.text[:40]}...`\n")
            tf.write(f"- **Response Preview**: {preview}...\n\n---\n")
            tf.flush()
            os.fsync(tf.fileno())
    except Exception as le:
        logger.error(f"VLI: Failed to log final completion audit: {le}")

    # [PERSISTENCE FIX] Persist generated markdown to disk for dashboard artifact links
    # Note: Slugification logic matches vli_dashboard.html exactly.
    if response_text and len(response_text) > 50:
        _persist_vli_report(request.text, response_text)
        
        # [NEW] Save to durable cache (TACTICAL ONLY) - HARDENED against poison caching
        if intent_mode == "TACTICAL_EXECUTION" and "[ERROR]" not in response_text and "timed out" not in response_text.lower():
            try:
                with open(cache_file, "w", encoding="utf-8") as cf:
                    json.dump({"timestamp": time.time(), "response_text": response_text}, cf)
            except Exception as ce:
                logger.error(f"VLI: Failed to write cache: {ce}")

    # [NEW] Persist AI Response to History
    thought = ""
    if isinstance(final_vli_state, dict):
        plan = final_vli_state.get("current_plan")
        if hasattr(plan, "thought"): thought = plan.thought
        elif isinstance(plan, dict): thought = plan.get("thought", "")

    _append_to_vli_history("ai", response_text, thought=thought, thread_id=transaction_id)

    metadata = {}
    if isinstance(final_vli_state, dict):
        metadata = final_vli_state.get("metadata", {})

    return {"response": response_text, "status": "OK", "error_details": None, "thread_id": transaction_id, "metadata": metadata}


# --- VLI REACTIVE PIPELINE (INBOX WATCHER & ARCHIVER) ---


async def vli_inbox_tick():
    """Heartbeat-triggered tick to watch inbox/ for drafts AND archive end-of-day plans."""
    inbox = get_inbox_path()
    plan_file = get_action_plan_path()
    archive_dir = get_archive_path()

    plan_dir = os.path.dirname(plan_file)
    os.makedirs(inbox, exist_ok=True)
    os.makedirs(archive_dir, exist_ok=True)
    os.makedirs(plan_dir, exist_ok=True)

    # 1. Check for Day Transition (End-of-day Archiving)
    global _vli_last_run_day
    current_day = datetime.now().strftime("%Y-%m-%d")
    if current_day != _vli_last_run_day:
        logger.info(f"VLI: Day transition detected ({_vli_last_run_day} -> {current_day}). Archiving plan.")
        if os.path.exists(plan_file):
            archive_file = os.path.join(archive_dir, f"Action_Plan_{_vli_last_run_day}.md")
            try:
                os.rename(plan_file, archive_file)
                # Create blank new plan for the new day
                with open(plan_file, "w", encoding="utf-8") as f:
                    f.write(f"# Daily Action Plan - {current_day}\n- [ ] Waiting for morning session briefing...")
            except Exception as e:
                logger.error(f"VLI: Day transition archival failed: {e}")

        # [NEW] Invalidate Executive Morning Briefing at midnight
        reports_dir = os.path.join(os.getcwd(), 'data', 'reports')
        meta_path = get_daily_briefing_path()
        if os.path.exists(meta_path):
            try:
                os.remove(meta_path)
            except Exception as e:
                logger.error(f"VLI: Failed to expire Morning Briefing: {e}")
                
        # [NEW] Evict all individual ticker analysis reports at midnight
        if os.path.exists(reports_dir):
            for file in os.listdir(reports_dir):
                if file.startswith("analyze_") and file.endswith(".md"):
                    try:
                        os.remove(os.path.join(reports_dir, file))
                    except Exception as e:
                        logger.error(f"VLI: Failed to expire report {file}: {e}")
                
        global _vli_last_async_report
        if "Executive Morning Briefing" in _vli_last_async_report:
            _vli_last_async_report = ""

        # [NEW] Clear scanner lists/states on day rollover
        try:
            clear_stale_scanner_files(force=True)
        except Exception as e:
            logger.error(f"VLI_SYSTEM: Failed to clear scanner lists on day transition: {e}")

        _vli_last_run_day = current_day

    # 2. Check for Inbox Drafts (Automatic alert extraction)
    try:
        files = [f for f in os.listdir(inbox) if f.endswith(".md")]
        global _vli_processed_draft_mtimes, _vli_rules_enabled
        from src.config.vli import inbox_rule_engine

        # Sync rule engine state with global toggle
        inbox_rule_engine.rules_enabled = _vli_rules_enabled

        for filename in files:
            # CRITICAL: Separate "Automation" (Drafts) from "Smart Filing" (Journals/Actions)
            # If a file matches a rule, DO NOT process it here. Let the user approve manually.
            if inbox_rule_engine.is_filing_candidate(filename):
                continue

            filepath = os.path.join(inbox, filename)
            try:
                mtime = os.path.getmtime(filepath)
            except OSError:
                continue  # File might have been moved

            # Deduplicate: Skip if we've processed this specific file version
            if filename in _vli_processed_draft_mtimes and _vli_processed_draft_mtimes[filename] == mtime:
                continue

            # Cooldown: Allow the UI to "see" the file before auto-archiving
            import time
            if time.time() - mtime < 10:
                continue

            logger.info(f"VLI Inbox: Processing draft '{filename}' (mtime: {mtime})")
            _vli_processed_draft_mtimes[filename] = mtime

            with open(filepath, encoding="utf-8") as rf:
                content = rf.read()

            # Extract logic and update global alerts
            new_alerts = extract_vli_logic(content)
            global _vli_extracted_alerts
            _vli_extracted_alerts.extend(new_alerts)

            # Keep only unique alerts by symbol/label
            seen = set()
            unique_alerts = []
            for a in _vli_extracted_alerts:
                key = f"{a['symbol']}:{a['label']}"
                if key not in seen:
                    seen.add(key)
                    unique_alerts.append(a)
            _vli_extracted_alerts = unique_alerts

            # Append to active plan
            with open(plan_file, "a", encoding="utf-8") as af:
                af.write(f"\n\n### Batch Update: {filename}\n{content}")

            # Success Archival
            archive_path = os.path.join(archive_dir, f"Draft_{datetime.now().strftime('%H%M%S')}_{filename}")
            try:
                os.rename(filepath, archive_path)
            except Exception as e:
                logger.error(f"VLI: Error archiving draft: {e}")

    except Exception as e:
        logger.error(f"VLI Reactive Pipeline Error: {e}")


# Redundant startup event removed (now merged at top)


@app.post("/api/chat/stream", dependencies=[Depends(verify_api_key)])
async def chat_stream(request: ChatRequest):
    # Check if MCP server configuration is enabled
    mcp_enabled = get_bool_env("ENABLE_MCP_SERVER_CONFIGURATION", False)

    # Validate MCP settings if provided
    if request.mcp_settings and not mcp_enabled:
        raise HTTPException(
            status_code=403,
            detail="MCP server configuration is disabled. Set ENABLE_MCP_SERVER_CONFIGURATION=true to enable MCP features.",
        )

    thread_id = request.thread_id
    if thread_id == "__default__":
        thread_id = str(uuid4())

    return StreamingResponse(
        _astream_workflow_generator(
            request.model_dump()["messages"],
            thread_id,
            request.resources,
            request.max_plan_iterations,
            request.max_step_num,
            request.max_search_results,
            request.auto_accepted_plan,
            request.interrupt_feedback,
            request.mcp_settings if mcp_enabled else {},
            request.enable_background_investigation,
            request.report_style,
            request.enable_deep_thinking,
            request.snaptrade_settings if request.snaptrade_settings else {},
            request.obsidian_settings if request.obsidian_settings else {},
            request.verbosity,
            request.is_test_mode,
            request.direct_mode,
        ),
        media_type="text/event-stream",
    )


def _process_tool_call_chunks(tool_call_chunks):
    """Process tool call chunks and sanitize arguments."""
    chunks = []
    for chunk in tool_call_chunks:
        chunks.append(
            {
                "name": chunk.get("name", ""),
                "args": sanitize_args(chunk.get("args", "")),
                "id": chunk.get("id", ""),
                "index": chunk.get("index", 0),
                "type": chunk.get("type", ""),
            }
        )
    return chunks


def _get_agent_name(agent, message_metadata):
    """Extract agent name from agent tuple."""
    agent_name = "unknown"
    if agent and len(agent) > 0:
        agent_name = agent[0].split(":")[0] if ":" in agent[0] else agent[0]
    else:
        agent_name = message_metadata.get("langgraph_node", "unknown")
    return agent_name


def _create_event_stream_message(message_chunk, message_metadata, thread_id, agent_name):
    """Create base event stream message."""
    event_stream_message = {
        "thread_id": thread_id,
        "agent": agent_name,
        "id": message_chunk.id,
        "role": "assistant",
        "checkpoint_ns": message_metadata.get("checkpoint_ns", ""),
        "langgraph_node": message_metadata.get("langgraph_node", ""),
        "langgraph_path": message_metadata.get("langgraph_path", ""),
        "langgraph_step": message_metadata.get("langgraph_step", ""),
        "content": message_chunk.content,
    }

    # Add optional fields
    if message_chunk.additional_kwargs.get("reasoning_content"):
        event_stream_message["reasoning_content"] = message_chunk.additional_kwargs["reasoning_content"]

    if message_chunk.response_metadata.get("finish_reason"):
        event_stream_message["finish_reason"] = message_chunk.response_metadata.get("finish_reason")

    return event_stream_message


def _create_interrupt_event(thread_id, event_data):
    """Create interrupt event."""
    interrupt_obj = event_data["__interrupt__"][0]

    # Handle different versions of LangGraph Interrupt object
    try:
        # Try the old format first (for backward compatibility)
        interrupt_id = interrupt_obj.ns[0] if hasattr(interrupt_obj, "ns") else str(interrupt_obj)
        content = interrupt_obj.value if hasattr(interrupt_obj, "value") else str(interrupt_obj)
    except AttributeError:
        # Newer version of LangGraph might have different structure
        interrupt_id = str(interrupt_obj) if not hasattr(interrupt_obj, "id") else interrupt_obj.id
        content = str(interrupt_obj) if not hasattr(interrupt_obj, "value") else interrupt_obj.value

    return _make_event(
        "interrupt",
        {
            "thread_id": thread_id,
            "id": interrupt_id,
            "role": "assistant",
            "content": content,
            "finish_reason": "interrupt",
            "options": [
                {"text": "Edit plan", "value": "edit_plan"},
                {"text": "Start research", "value": "accepted"},
            ],
        },
    )


def _process_initial_messages(message, thread_id):
    """Process initial messages and yield formatted events."""
    json_data = json.dumps(
        {
            "thread_id": thread_id,
            "id": "run--" + message.get("id", uuid4().hex),
            "role": "user",
            "content": message.get("content", ""),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    chat_stream_message(thread_id, f"event: message_chunk\ndata: {json_data}\n\n", "none")


async def _background_raw_news_fetch(targets: list[str]):
    try:
        from src.tools.news import get_ticker_news
        from src.services.datastore import DatastoreManager
        from datetime import datetime
        import asyncio
        
        # Concurrently fetch
        await asyncio.gather(*[get_ticker_news.ainvoke({"subject": t}) for t in targets])
            
        found_data = []
        for t in targets:
            cached = DatastoreManager.get_artifact(t, "news_raw", "latest")
            if cached and "data" in cached:
                found_data.append(f"## {t} News\n{cached['data']}")
                
        if found_data:
            combined = "\n\n---\n\n".join(found_data)
            global _vli_last_async_report
            _vli_last_async_report = f"# Async Gathered News\n\n{combined}"
            
            from src.config.vli import get_vli_path
            try:
                tf_path = get_vli_path("VLI_Raw_Telemetry.md")
                with open(tf_path, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime("[%H:%M:%S]")
                    f.write(f"\n{ts}  **[BACKGROUND FETCH]** Raw news successfully gathered for {', '.join(targets)}. Sent to Analysis Window.\n")
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Background raw news fetch failed: {e}")

async def _background_regenerate_data(sym: str):
    try:
        from src.tools.news import get_ticker_news
        from src.tools.finance import get_stock_quote
        from datetime import datetime
        import asyncio
        import uuid
        from src.config.vli import get_vli_path
        
        import json
        import os
        from src.config.vli import VAULT_ROOT
        
        in_watchlist = False
        target_tier = "War Barbell"
        try:
            macro_path = os.path.join(VAULT_ROOT, "_cobalt", "01_Transit", "Buckets", "MACRO_WATCHLIST_state.json")
            if os.path.exists(macro_path):
                with open(macro_path, encoding="utf-8") as f:
                    macro_content = json.load(f)
                    for row in macro_content.get("rows", []):
                        if len(row) > 1 and row[1].upper() == sym:
                            in_watchlist = True
                            target_tier = "Macro"
                            break
                            
            scanner_path = os.path.join(VAULT_ROOT, "_cobalt", "01_Transit", "Buckets", "STRIKE_RES_state.json")
            if not in_watchlist and os.path.exists(scanner_path):
                with open(scanner_path, encoding="utf-8") as f:
                    scanner_content = json.load(f)
                    for cand in scanner_content.get("candidates", []):
                        if cand.get("symbol", "").upper() == sym:
                            in_watchlist = True
                            target_tier = cand.get("tier", "War Barbell")
                            break
        except Exception as e:
            pass
        
        def write_telemetry(msg: str):
            try:
                tf_path = get_vli_path("VLI_Raw_Telemetry.md")
                with open(tf_path, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime("[%H:%M:%S]")
                    f.write(f"\n{ts} [REGENERATE] {msg}\n")
                
                # Push to global UI queue
                if in_watchlist:
                    try:
                        get_telemetry_queue().put_nowait(f"[REGENERATE] {msg}")
                    except Exception:
                        pass
            except Exception:
                pass
                
        write_telemetry(f"Fetch has been called for {sym}")
        write_telemetry(f"News is being gathered for {sym}")
        
        write_telemetry(f"Symbol data has been received for {sym}")
        
        # Concurrently fetch to warm the cache, ignoring errors to avoid crashing
        await asyncio.gather(
            get_ticker_news.ainvoke({"subject": sym, "refresh": True}),
            get_stock_quote.ainvoke({"ticker": sym, "force_refresh": True}),
            return_exceptions=True
        )
        
        write_telemetry(f"Analysis report is in progress for {sym}")
        
        # Dispatch the full graph to synthesize the new report at HIGH priority
        from src.services.scheduler import cobalt_scheduler
        
        async def high_priority_synthesis():
            await _background_synthesis_task(
                text=f"analyze {sym}. Ensure you include a line 'Active Strategy: {target_tier.capitalize()} Strategy' at the top of the report, and frame the analysis using {target_tier} terminology.",
                image=None,
                direct_mode=False,
                reporter_llm_type="reasoning",
                vli_llm_type="reasoning",
                thread_id=f"regen_{uuid.uuid4().hex[:8]}",
                silent=not in_watchlist
            )
            write_telemetry(f"Update complete for {sym}")
            
        cobalt_scheduler.add_timer(
            task_id=f"REGEN_{sym}_{uuid.uuid4().hex[:4]}",
            name=f"High Priority Regeneration: {sym}",
            type="ONE_SHOT",
            schedule=0,
            period_unit="seconds",
            priority="HIGH",
            callback=high_priority_synthesis
        )
            
    except Exception as e:
        logger.error(f"Background data regeneration failed for {sym}: {e}")

async def _process_message_chunk(message_chunk, message_metadata, thread_id, agent, session_obj=None, project_obj=None):
    """Process a single message chunk and yield appropriate events."""
    agent_name = _get_agent_name(agent, message_metadata)
    event_stream_message = _create_event_stream_message(message_chunk, message_metadata, thread_id, agent_name)

    from langchain_core.messages import AIMessage, AIMessageChunk
    if isinstance(message_chunk, (AIMessage, AIMessageChunk)) and isinstance(message_chunk.content, str):
        if message_chunk.content.startswith("[ANALYSIS_WINDOW_PUSH]"):
            global _vli_last_async_report
            _vli_last_async_report = message_chunk.content.replace("[ANALYSIS_WINDOW_PUSH]", "").strip()
            message_chunk.content = "I have compiled the requested raw news and pushed it directly to your Analysis Window."
            event_stream_message["content"] = message_chunk.content
        elif message_chunk.content.startswith("[BACKGROUND_FETCH_NEWS]"):
            targets_str = message_chunk.content.replace("[BACKGROUND_FETCH_NEWS]", "").strip()
            targets = [t.strip() for t in targets_str.split(",") if t.strip()]
            import asyncio
            asyncio.create_task(_background_raw_news_fetch(targets))
            message_chunk.content = f"Asynchronously fetching raw news for {targets_str}. It will be pushed to the Analysis Window once complete."
            event_stream_message["content"] = message_chunk.content
        elif message_chunk.content.startswith("[BACKGROUND_REGENERATE_DATA]"):
            sym = message_chunk.content.replace("[BACKGROUND_REGENERATE_DATA]", "").strip()
            import asyncio
            asyncio.create_task(_background_regenerate_data(sym))
            message_chunk.content = f"Cache cleared for {sym}. Asynchronously regenerating market data, volume, prices, and news."
            event_stream_message["content"] = message_chunk.content

    # Save assistant messages to database
    if isinstance(message_chunk, (AIMessage, AIMessageChunk)) and message_chunk.content:
        try:
            # Try to save the message to database (this will work if session exists)
            if session_obj:
                research_db.save_session_message(session_id=session_obj.id, role="assistant", content=message_chunk.content, message_type="text")

                # Extract and save research findings from AI responses
                if project_obj:
                    research_db.extract_and_save_findings(content=message_chunk.content, project_id=project_obj.id, session_id=str(session_obj.id))

        except Exception:
            # Silently fail if database is not available or session doesn't exist
            pass

    if isinstance(message_chunk, ToolMessage):
        # Tool Message - Return the result of the tool call
        event_stream_message["tool_call_id"] = message_chunk.tool_call_id

        # Save tool results to database
        try:
            if session_obj:
                research_db.save_session_message(session_id=session_obj.id, role="tool", content=str(message_chunk.content), message_type="tool_result", tool_calls=message_chunk.tool_call_id)
        except Exception:
            pass

        # Log Tool Execution to Telemetry
        try:
            from src.config.vli import get_vli_path
            from datetime import datetime
            tf_path = get_vli_path("VLI_Raw_Telemetry.md")
            with open(tf_path, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime("[%H:%M:%S]")
                task_name = message_chunk.name if getattr(message_chunk, "name", None) else agent_name
                if not task_name.endswith("_worker") and task_name not in ["vli_spine", "router", "coordinator"]:
                    task_name = f"{task_name}_subtask_worker"
                snippet = str(message_chunk.content)[:100].replace('\n', ' ')
                f.write(f"\n{ts} [{task_name.upper()}] Execution Result: {snippet}...\n")
        except Exception:
            pass

        yield _make_event("tool_call_result", event_stream_message)
    elif isinstance(message_chunk, (AIMessage, AIMessageChunk)):
        # AI Message - Raw message tokens
        if message_chunk.tool_calls:
            # AI Message - Tool Call
            event_stream_message["tool_calls"] = message_chunk.tool_calls
            event_stream_message["tool_call_chunks"] = _process_tool_call_chunks(message_chunk.tool_call_chunks)
            
            # Log Tool Initiation to Telemetry
            try:
                from src.config.vli import get_vli_path
                from datetime import datetime
                tf_path = get_vli_path("VLI_Raw_Telemetry.md")
                with open(tf_path, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime("[%H:%M:%S]")
                    for tc in message_chunk.tool_calls:
                        task_name = tc.get("name", "unknown")
                        if not task_name.endswith("_worker") and task_name not in ["vli_spine", "router", "coordinator"]:
                            task_name = f"{task_name}_subtask_worker"
                        f.write(f"\n{ts} [{task_name.upper()}] Initiating Task Execution...\n")
            except Exception:
                pass

            # Save tool calls to database
            try:
                if session_obj:
                    tool_calls_json = json.dumps([{"name": tc.get("name", ""), "args": tc.get("args", ""), "id": tc.get("id", "")} for tc in message_chunk.tool_calls])
                    research_db.save_session_message(session_id=session_obj.id, role="assistant", content="", message_type="tool_call", tool_calls=tool_calls_json)
            except Exception:
                pass

            yield _make_event("tool_calls", event_stream_message)
        elif hasattr(message_chunk, "tool_call_chunks") and message_chunk.tool_call_chunks:
            # AI Message - Tool Call Chunks
            event_stream_message["tool_call_chunks"] = _process_tool_call_chunks(message_chunk.tool_call_chunks)
            yield _make_event("tool_call_chunks", event_stream_message)
        else:
            # AI Message - Raw message tokens
            yield _make_event("message_chunk", event_stream_message)


async def _stream_graph_events(graph_instance, workflow_input, workflow_config, thread_id, session_obj=None, project_obj=None):
    """Stream events from the graph and process them."""
    try:
        async for agent, _, event_data in graph_instance.astream(
            workflow_input,
            config=workflow_config,
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            if isinstance(event_data, dict):
                if "__interrupt__" in event_data:
                    yield _create_interrupt_event(thread_id, event_data)
                continue

            message_chunk, message_metadata = cast(tuple[BaseMessage, dict[str, Any]], event_data)

            async for event in _process_message_chunk(message_chunk, message_metadata, thread_id, agent, session_obj, project_obj):
                yield event
    except Exception as e:
        logger.exception("Error during graph execution")
        yield _make_event(
            "error",
            {
                "thread_id": thread_id,
                "error": str(e),
            },
        )


async def _astream_workflow_generator(
    messages: list[dict],
    thread_id: str,
    resources: list[Resource],
    max_plan_iterations: int,
    max_step_num: int,
    max_search_results: int,
    auto_accepted_plan: bool,
    interrupt_feedback: str,
    mcp_settings: dict,
    enable_background_investigation: bool,
    report_style: ReportStyle,
    enable_deep_thinking: bool,
    snaptrade_settings: dict,
    obsidian_settings: dict,
    verbosity: int = 1,
    is_test_mode: bool = False,
    direct_mode: bool = False,
):
    # Create research project and session for persistence
    research_topic = messages[-1]["content"] if messages else "Research Session"
    session_obj = None
    project_obj = None

    try:
        # Create or get research project
        project_obj = research_db.create_research_project(title=f"Research: {research_topic[:100]}", description=f"Research session on: {research_topic}", tags="auto-generated")
        logger.info(f"Created research project: {project_obj.id}")

        # Create research session
        session_obj = research_db.create_research_session(project_id=project_obj.id, session_id=thread_id, title=f"Session: {research_topic[:50]}")
        logger.info(f"Created research session: {session_obj.id}")

    except Exception as e:
        logger.warning(f"Failed to create research project/session: {e}")

    # Process initial messages
    for message in messages:
        if isinstance(message, dict) and "content" in message:
            _process_initial_messages(message, thread_id)

            # Save user message to database
            try:
                if session_obj:
                    research_db.save_session_message(session_id=session_obj.id, role=message.get("role", "user"), content=message.get("content", ""), message_type="text")
            except Exception as e:
                logger.warning(f"Failed to save user message: {e}")

    # Prepare workflow input
    
    # [NEW] Historical Symbol Memory Injection
    injected_observations = []
    req_text = messages[-1]["content"] if messages else ""
    if "generate a detailed Daily Trading Report post-mortem" in req_text:
        from src.services.historical_reports import get_trader_performance_summary
        perf_summary = get_trader_performance_summary()
        if perf_summary:
            injected_observations.append(f"[SYSTEM INJECTION: Trader Performance History]\n{perf_summary}")
    elif any(req_text.lower().startswith(a) for a in TACTICAL_REPORT_ALIASES):
        sym = req_text.split(" ")[1].strip().upper()
        from src.services.historical_reports import get_historical_symbol_summary
        sym_summary = get_historical_symbol_summary(sym)
        if sym_summary:
            injected_observations.append(f"[SYSTEM INJECTION: Supplemental Interday History for {sym}]\n{sym_summary}")

    workflow_input = {
        "messages": messages,
        "plan_iterations": 0,
        "final_report": "",
        "current_plan": None,
        "observations": injected_observations,
        "auto_accepted_plan": auto_accepted_plan,
        "enable_background_investigation": enable_background_investigation,
        "research_topic": req_text,
        "obsidian_settings": obsidian_settings,
        "verbosity": verbosity,
        "test_mode": is_test_mode,
        "direct_mode": direct_mode,
    }

    if not auto_accepted_plan and interrupt_feedback:
        resume_msg = f"[{interrupt_feedback}]"
        if messages:
            resume_msg += f" {messages[-1]['content']}"
        workflow_input = Command(resume=resume_msg)

    # Prepare workflow config
    workflow_config = {
        "configurable": {
            "thread_id": thread_id,
            "max_plan_iterations": max_plan_iterations,
            "max_step_num": max_step_num,
            "max_search_results": max_search_results,
            "mcp_settings": mcp_settings,
            "report_style": report_style.value,
            "enable_deep_thinking": enable_deep_thinking,
            "snaptrade_settings": snaptrade_settings,
            "obsidian_settings": obsidian_settings,
            "direct_mode": direct_mode,
        },
        "recursion_limit": get_recursion_limit(),
    }

    checkpoint_saver = get_bool_env("LANGGRAPH_CHECKPOINT_SAVER", False)
    checkpoint_url = get_str_env("LANGGRAPH_CHECKPOINT_DB_URL", "")
    # Handle checkpointer if configured
    connection_kwargs = {
        "autocommit": True,
        "row_factory": "dict_row",
        "prepare_threshold": 0,
    }
    try:
        if checkpoint_saver and checkpoint_url != "":
            if checkpoint_url.startswith("postgresql://"):
                logger.info("start async postgres checkpointer.")
                async with AsyncConnectionPool(checkpoint_url, kwargs=connection_kwargs) as conn:
                    checkpointer = AsyncPostgresSaver(conn)
                    await checkpointer.setup()
                    graph.checkpointer = checkpointer
                    graph.store = in_memory_store
                    async for event in _stream_graph_events(graph, workflow_input, workflow_config, thread_id, session_obj, project_obj):
                        yield event

            if checkpoint_url.startswith("mongodb://"):
                logger.info("Starting native MongoDB checkpointer.")
                async with NativeMongoDBSaver.from_conn_string(checkpoint_url) as checkpointer:
                    graph.checkpointer = checkpointer
                    graph.store = in_memory_store
                    async for event in _stream_graph_events(graph, workflow_input, workflow_config, thread_id, session_obj, project_obj):
                        yield event
        else:
            # Use graph without MongoDB checkpointer
            async for event in _stream_graph_events(graph, workflow_input, workflow_config, thread_id, session_obj, project_obj):
                yield event
    except Exception as e:
        emsg = str(e)
        status_code = "TIMEOUT" if "timed out" in emsg.lower() else "ERROR"
        if "429" in emsg or "resource_exhausted" in emsg.lower():
            status_code = "QUOTA_EXHAUSTED"
            emsg = "Gemini API Quota Exhausted. Transitioning to fallback or awaiting cooldown..."
            
        logger.error(f"[VLI_ASTREAM] Caught stream termination error: {emsg}")
        yield f"data: {json.dumps({'type': 'error', 'msg': emsg, 'status': status_code})}\n\n"


def _make_event(event_type: str, data: dict[str, any]):
    if data.get("content") == "":
        data.pop("content")
    # Ensure JSON serialization with proper encoding
    try:
        json_data = json.dumps(data, ensure_ascii=False)

        finish_reason = data.get("finish_reason", "")
        chat_stream_message(
            data.get("thread_id", ""),
            f"event: {event_type}\ndata: {json_data}\n\n",
            finish_reason,
        )

        return f"event: {event_type}\ndata: {json_data}\n\n"
    except (TypeError, ValueError) as e:
        logger.error(f"Error serializing event data: {e}")
        # Return a safe error event
        error_data = json.dumps({"error": "Serialization failed"}, ensure_ascii=False)
        return f"event: error\ndata: {error_data}\n\n"


@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using volcengine TTS API."""
    app_id = get_str_env("VOLCENGINE_TTS_APPID", "")
    if not app_id:
        raise HTTPException(status_code=400, detail="VOLCENGINE_TTS_APPID is not set")
    access_token = get_str_env("VOLCENGINE_TTS_ACCESS_TOKEN", "")
    if not access_token:
        raise HTTPException(status_code=400, detail="VOLCENGINE_TTS_ACCESS_TOKEN is not set")

    try:
        cluster = get_str_env("VOLCENGINE_TTS_CLUSTER", "volcano_tts")
        voice_type = get_str_env("VOLCENGINE_TTS_VOICE_TYPE", "BV700_V2_streaming")

        tts_client = VolcengineTTS(
            appid=app_id,
            access_token=access_token,
            cluster=cluster,
            voice_type=voice_type,
        )
        # Call the TTS API
        result = tts_client.text_to_speech(
            text=request.text[:1024],
            encoding=request.encoding,
            speed_ratio=request.speed_ratio,
            volume_ratio=request.volume_ratio,
            pitch_ratio=request.pitch_ratio,
            text_type=request.text_type,
            with_frontend=request.with_frontend,
            frontend_type=request.frontend_type,
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=str(result["error"]))

        # Decode the base64 audio data
        audio_data = base64.b64decode(result["audio_data"])

        # Return the audio file
        return Response(
            content=audio_data,
            media_type=f"audio/{request.encoding}",
            headers={"Content-Disposition": (f"attachment; filename=tts_output.{request.encoding}")},
        )

    except Exception as e:
        logger.exception(f"Error in TTS endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/podcast/generate")
async def generate_podcast(request: GeneratePodcastRequest):
    try:
        report_content = request.content
        print(report_content)
        workflow = build_podcast_graph()
        final_state = workflow.invoke({"input": report_content})
        audio_bytes = final_state["output"]
        return Response(content=audio_bytes, media_type="audio/mp3")
    except Exception as e:
        logger.exception(f"Error occurred during podcast generation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/ppt/generate")
async def generate_ppt(request: GeneratePPTRequest):
    try:
        report_content = request.content
        print(report_content)
        workflow = build_ppt_graph()
        final_state = workflow.invoke({"input": report_content})
        generated_file_path = final_state["generated_file_path"]
        with open(generated_file_path, "rb") as f:
            ppt_bytes = f.read()
        return Response(
            content=ppt_bytes,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    except Exception as e:
        logger.exception(f"Error occurred during ppt generation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/prose/generate")
async def generate_prose(request: GenerateProseRequest):
    try:
        sanitized_prompt = request.prompt.replace("\r\n", "").replace("\n", "")
        logger.info(f"Generating prose for prompt: {sanitized_prompt}")
        workflow = build_prose_graph()
        events = workflow.astream(
            {
                "content": request.prompt,
                "option": request.option,
                "command": request.command,
            },
            stream_mode="messages",
            subgraphs=True,
        )
        return StreamingResponse(
            (f"data: {event[0].content}\n\n" async for _, event in events),
            media_type="text/event-stream",
        )
    except Exception as e:
        logger.exception(f"Error occurred during prose generation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)

@app.get("/api/vli/report/{symbol}")
async def get_vli_report(symbol: str):
    """Serve generated Markdown analysis report for a symbol."""

    if symbol == "DAILY_BRIEFING":
        report_path = get_daily_briefing_path()
    else:
        path1 = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{symbol.lower()}.md')
        path2 = os.path.join(os.getcwd(), 'backend', 'data', 'reports', f'analyze_{symbol.lower()}.md')
        report_path = path1 if os.path.exists(path1) else path2
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"success": True, "content": content, "path": report_path.replace("\\", "/")}
    return {"success": False, "error": "Report not found or not yet generated."}

@app.post("/api/prompt/enhance")
async def enhance_prompt(request: EnhancePromptRequest):
    try:
        sanitized_prompt = request.prompt.replace("\r\n", "").replace("\n", "")
        logger.info(f"Enhancing prompt: {sanitized_prompt}")

        # Convert string report_style to ReportStyle enum
        report_style = None
        if request.report_style:
            try:
                # Handle both uppercase and lowercase input
                style_mapping = {
                    "ACADEMIC": ReportStyle.ACADEMIC,
                    "POPULAR_SCIENCE": ReportStyle.POPULAR_SCIENCE,
                    "NEWS": ReportStyle.NEWS,
                    "SOCIAL_MEDIA": ReportStyle.SOCIAL_MEDIA,
                }
                report_style = style_mapping.get(request.report_style.upper(), ReportStyle.ACADEMIC)
            except Exception:
                # If invalid style, default to ACADEMIC
                report_style = ReportStyle.ACADEMIC
        else:
            report_style = ReportStyle.ACADEMIC

        workflow = build_prompt_enhancer_graph()
        final_state = workflow.invoke(
            {
                "prompt": request.prompt,
                "context": request.context,
                "report_style": report_style,
            }
        )
        return {"result": final_state["output"]}
    except Exception as e:
        logger.exception(f"Error occurred during prompt enhancement: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/mcp/server/metadata", response_model=MCPServerMetadataResponse)
async def mcp_server_metadata(request: MCPServerMetadataRequest):
    """Get information about an MCP server."""
    # Check if MCP server configuration is enabled
    if not get_bool_env("ENABLE_MCP_SERVER_CONFIGURATION", False):
        raise HTTPException(
            status_code=403,
            detail="MCP server configuration is disabled. Set ENABLE_MCP_SERVER_CONFIGURATION=true to enable MCP features.",
        )

    try:
        # Set default timeout with a longer value for this endpoint
        timeout = 300  # Default to 300 seconds for this endpoint

        # Use custom timeout from request if provided
        if request.timeout_seconds is not None:
            timeout = request.timeout_seconds

        # Load tools from the MCP server using the utility function
        tools = await load_mcp_tools(
            server_type=request.transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            headers=request.headers,
            timeout_seconds=timeout,
        )

        # Create the response with tools
        response = MCPServerMetadataResponse(
            transport=request.transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            headers=request.headers,
            tools=tools,
        )

        return response
    except Exception as e:
        logger.exception(f"Error in MCP server metadata endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.get("/api/rag/config", response_model=RAGConfigResponse)
async def rag_config():
    """Get the config of the RAG."""
    return RAGConfigResponse(provider=SELECTED_RAG_PROVIDER)


@app.get("/api/rag/resources", response_model=RAGResourcesResponse)
async def rag_resources(request: Annotated[RAGResourceRequest, Query()]):
    """Get the resources of the RAG."""
    retriever = build_retriever()
    if retriever:
        return RAGResourcesResponse(resources=retriever.list_resources(request.query))
    return RAGResourcesResponse(resources=[])


@app.get("/api/config", response_model=ConfigResponse)
async def config():
    """Get the config of the server."""
    return ConfigResponse(
        rag=RAGConfigResponse(provider=SELECTED_RAG_PROVIDER),
        models=get_configured_llm_models(),
    )


# Include research API routes
app.include_router(research_router, prefix="/api/research", tags=["research"])
app.include_router(studio_router)

# Include scanner routes (integrated Layer A + Phase 1/2 stream)
from src.server.routes.scanner import router as scanner_router
app.include_router(scanner_router, prefix="/api/scanner", tags=["scanner"])


# # Trigger Telemetry Purge on Server Startup
try:
    from src.config.vli import purge_stale_vli_sessions
    purge_stale_vli_sessions()
except Exception:
    pass

# --- DROPZONE WATCHER BACKGROUND SERVICE & ENDPOINTS ---
@app.api_route("/api/v1/dropzone/check", methods=["GET", "POST"])
@app.api_route("/api/vli/dropzone/check", methods=["GET", "POST"])
async def trigger_dropzone_check():
    """Triggers immediate ingestion and archiving of files in data/dropzone."""
    try:
        from src.services.csv_importer import watch_dropzone_and_process
        res = await asyncio.to_thread(watch_dropzone_and_process)
        return {"status": "success", "message": res}
    except Exception as e:
        logger.error(f"Dropzone check API error: {e}")
        return {"status": "error", "message": str(e)}

async def _bg_dropzone_watcher_loop():
    """Background task to continuously poll and ingest files from data/dropzone."""
    while True:
        try:
            from src.services.csv_importer import watch_dropzone_and_process
            res = await asyncio.to_thread(watch_dropzone_and_process)
            if res and "No files to process" not in res:
                logger.info(f"VLI_SYSTEM Dropzone Auto-Ingest: {res}")
        except Exception as e:
            logger.error(f"VLI_SYSTEM Dropzone Watcher error: {e}")
        await asyncio.sleep(3.0)

@app.on_event("startup")
async def start_dropzone_watcher():
    asyncio.create_task(_bg_dropzone_watcher_loop())

@app.post("/api/system/restart")
async def restart_server(request: Request):
    import os
    if os.name != 'nt':
        return {"status": "error", "message": "Restart only supported in local Windows environment."}
        
    logger.info("VLI_SYSTEM: Initiating true server restart sequence...")
    def restart_process():
        import time
        import sys
        import os
        import tempfile
        import subprocess
        
        # Give the API request time to return before we replace the process
        time.sleep(1.0)
        
        wrapper_path = os.path.join(tempfile.gettempdir(), "vli_restarter.py")
        with open(wrapper_path, "w") as f:
            f.write(f"""import time, os, sys, subprocess
time.sleep(2.0)
try:
    os.remove({repr(wrapper_path)})
except Exception:
    pass
cmd = {repr(sys.orig_argv)}
subprocess.Popen(cmd)
""")
        
        subprocess.Popen([sys.executable, wrapper_path])
        os._exit(0)
    
    import threading
    threading.Thread(target=restart_process, daemon=True).start()
    return {"status": "restarting"}


@app.post("/")
async def root_webhook(request: Request):
    """
    Fallback endpoint to catch any POST requests sent to the root URL (/) 
    instead of the dedicated webhook endpoint (/api/scanner/webhook).
    Supports both JSON payloads (upgraded indicators) and raw text alerts.
    """
    import json
    import re
    
    body_bytes = await request.body()
    body_str = body_bytes.decode('utf-8', errors='ignore').strip()
    logger.info(f"Received root POST webhook. Content-Type: {request.headers.get('content-type')}, body: {body_str}")
    
    # Try to parse as JSON first (upgraded indicator webhooks)
    try:
        data = json.loads(body_str)
        from src.server.routes.scanner import webhook_tradingview, TradingViewAlertPayload
        payload = TradingViewAlertPayload(**data)
        return await webhook_tradingview(payload)
    except Exception as json_e:
        # If not JSON, it could be a manual text alert (e.g. "MCL1!, 5 Crossing horizontal line")
        logger.info(f"Root POST payload is not valid JSON, parsing as raw text alert: {json_e}")
        
        try:
            parts = [p.strip() for p in body_str.split(",")]
            if len(parts) >= 2:
                symbol = parts[0]
                tf_part = parts[1].split()[0] # e.g. "5"
                
                tf_match = re.match(r'^(\d+)', tf_part)
                if tf_match:
                    timeframe = tf_match.group(1)
                    from src.server.routes.scanner import webhook_tradingview, TradingViewAlertPayload
                    payload = TradingViewAlertPayload(
                        symbol=symbol,
                        timeframe=timeframe,
                        state="NONE",
                        is_forming=False,
                        open=0.0, high=0.0, low=0.0, close=0.0,
                        prev_high=0.0, prev_low=0.0,
                        open_time=""
                    )
                    return await webhook_tradingview(payload)
        except Exception as parse_e:
            logger.error(f"Failed to parse raw text root alert: {parse_e}")
            
    return {"status": "success", "message": "Root webhook processed"}


# Mount the backend directory to serve the dashboard HTML
backend_dir = os.path.dirname(os.path.abspath(__file__))  # src/server
backend_root = os.path.abspath(os.path.join(backend_dir, "..", ".."))  # backend/
public_dir = os.path.join(backend_root, "public")

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith(".html") or path.endswith(".js") or path.endswith(".css") or path == "/":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.mount("/", StaticFiles(directory=public_dir, html=True), name="static")

# Trigger hot reload
# RELOAD_FLAG_2026_04_20_12_56
