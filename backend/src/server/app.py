# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

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

# Global queue for pushing telemetry directly to the UI
global_telemetry_queue = None

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
    leak_keywords = ["SECURITY OVERRIDE", "APEX 500 SYSTEM", "SYSTEM INSTRUCTION", "USER IDENTITY", "OPERATIONAL MANDATE", "EXPECTED DICT", "SYSTEMMESSAGE"]
    if any(k in upper_content for k in leak_keywords):
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
        return filename
    except Exception as e:
        logger.error(f"VLI_SYSTEM: Failed to persist report '{filename}': {e}")
        return None


def _get_vli_intent(text: str) -> str:
    """Standardized intent classification for Market Insight vs Tactical Execution."""
    text_trim = text.strip()
    text_upper = text_trim.upper()
    is_smc = "SMC" in text_upper
    
    tactical_triggers = ["ANALYZE", "ANALYSIS", "STRIKE", "SIGNAL", "SMC", "ENTRY", "SCAN", "SWORD", "SHIELD", "SETUP", "TRADE", "EXECUTE"]
    educational_markers = ["LEARN", "EDUCATION", "EXPLAIN", "CONCEPT", "VS", "COMPARE", "PERFORM", "KEEP UP", "YTD", "YEAR", "GIVEN", "OUTLOOK", "SCENARIO", "RECOMMEND", "SUGGEST", "DOES", "HOW"]
    
    is_tactical = any(kw in text_upper for kw in tactical_triggers) or is_smc
    is_educational = any(kw in text_upper for kw in educational_markers)
    
    if is_tactical and not is_educational:
        return "TACTICAL_EXECUTION"
        
    question_starters = ["WHAT", "HOW", "WHY", "WHEN", "WHICH", "IS", "CAN", "WHO", "WHOSE", "WHOM", "ARE", "DIFFERENCE", "WILL", "DOES", "COULD", "SHOULD"]
    is_question = any(text_upper.startswith(qs) for qs in question_starters) or text_trim.endswith("?") or text_trim.endswith("!")
    
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

app = FastAPI(title="Cobalt Multi-Agent (CMA) - VibeLink Interface", description="Institutional-grade agentic financial monitoring pipeline.", version="10.2.1")

@app.get("/api/telemetry/stream")
async def ui_telemetry_stream():
    """Streams global telemetry events to the UI."""
    async def event_generator():
        while True:
            msg = await get_telemetry_queue().get()
            yield f"data: {json.dumps({'type': 'telemetry', 'msg': msg})}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")



@app.get("/api/health")
async def health_check():
    try:
        from src.version import SERVER_VERSION
        return {"status": "ok", "version": SERVER_VERSION}
    except ImportError:
        return {"status": "ok", "version": "00.000.0000"}

@app.post("/api/system/restart")
async def system_restart():
    logger.warning("VLI_SYSTEM: Received restart signal from client.")
    import threading
    import sys
    import subprocess
    def delay_exit():
        import time
        time.sleep(1)
        # Re-launch the current process
        subprocess.Popen([sys.executable] + sys.argv)
        os._exit(0)
    threading.Thread(target=delay_exit).start()
    return {"status": "restarting"}

@app.get("/vli")
async def vli_dashboard_redirect():
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/vli_dashboard.html")


# Add CORS middleware
# It's recommended to load the allowed origins from an environment variable
# for better security and flexibility across different environments.
allowed_origins_str = get_str_env("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8089,http://127.0.0.1:8089,http://localhost:8000,http://127.0.0.1:8000,https://digital.fidelity.com")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]

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
    Automated 5-minute watchdog tracing the SCANNER_COMBAT_LIST for
    intraday Break of Structure (BOS) and Change of Character (CHOCH) patterns.
    """
    import json
    from src.tools.smc import run_smc_analysis
    
    combat_list_path = os.path.join(os.getcwd(), "data", "SCANNER_COMBAT_LIST.json")
    # Correcting dynamic pathing just in case
    if not os.path.exists(combat_list_path):
        combat_list_path = os.path.join(os.getcwd(), "backend", "data", "SCANNER_COMBAT_LIST.json")
        if not os.path.exists(combat_list_path):
            return

    try:
        with open(combat_list_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        candidates = data.get("candidates", [])
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
                msg = f"🚨 **[SMC ALERT]**: Just detected an Institutional **{trigger_type}** footprint printed on the **5m** structural timeframe for **{symbol}**."
                
                # Push organically to the Command Center UI via chat proxy
                _append_to_vli_history("Analyst", msg)
                logger.info(f"[SMC WATCHDOG] Trigger payload fired for {symbol} ({trigger_type})")
                
    except Exception as e:
        logger.error(f"[SMC WATCHDOG] Internal polling failure: {e}")

async def poll_market_pulse():
    """
    Automated execution of Phase 1 and Phase 2 algorithmic pulse tracking.
    Refreshes the SCANNER_RES_state.json natively without broadcasting terminal SSEs.
    """
    from datetime import datetime
    from src.config.vli import get_vli_path
    from src.tools.scanner import _build_session_watchlist_impl, _run_activity_pulse_impl, sanitize_data, NpEncoder

    try:
        combat_list_path = os.path.join(os.getcwd(), "data", "SCANNER_COMBAT_LIST.json")
        if not os.path.exists(combat_list_path):
            combat_list_path = os.path.join(os.getcwd(), "backend", "data", "SCANNER_COMBAT_LIST.json")

        phase0_raw = []
        if os.path.exists(combat_list_path):
            with open(combat_list_path, "r", encoding="utf-8") as f:
                c_data = json.load(f)
                phase0_raw = c_data.get("combat_list", [])
                
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
        transit_path = get_vli_path(os.path.join("01_Transit", "Buckets", "SCANNER_RES_state.json"))
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
    import sys
    try:
        script_path = os.path.join(os.getcwd(), "scripts", "tv_scanner_sync.py")
        if not os.path.exists(script_path):
            script_path = os.path.join(os.getcwd(), "backend", "scripts", "tv_scanner_sync.py")
            
        logger.info(f"[TV SYNC] Launching TradingView extractor: {script_path}")
        process = await asyncio.create_subprocess_exec(
            sys.executable, script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"[TV SYNC] Sync returned non-zero code. Error output: {stderr.decode('utf-8', errors='ignore')}")

    except Exception as e:
        logger.error(f"[TV SYNC] Synchronization failed: {e}")

async def run_idle_analysis(manual_trigger: bool = False):
    """
    Background orchestrator that diffs the scanner state against generated reports
    and spawns analysis agents for any missing symbols with stagger logic.
    """
    import asyncio
    from datetime import datetime
    
    target_path = os.path.join(os.getcwd(), 'data', 'SCANNER_COMBAT_LIST.json')
    shield_path = os.path.join(os.getcwd(), 'data', 'SHIELD_COMBAT_LIST.json')
    if not os.path.exists(target_path) and not os.path.exists(shield_path):
        return
        
    candidates = []
    try:
        if os.path.exists(target_path):
            with open(target_path, 'r') as f:
                state = json.load(f)
            candidates.extend(state.get("candidates", []) or state.get("combat_list", []))
            
        shield_path = os.path.join(os.getcwd(), 'data', 'SHIELD_COMBAT_LIST.json')
        if os.path.exists(shield_path):
            with open(shield_path, 'r') as f:
                s_state = json.load(f)
            candidates.extend(s_state.get("combat_list", []))
    except Exception as e:
        logger.error(f"[BG_ANALYST] Failed to read combat lists: {e}")

    try:
        from src.config.vli import get_vli_path
        macro_path = get_vli_path(os.path.join("01_Transit", "Buckets", "MACRO_WATCHLIST_state.json"))
        if os.path.exists(macro_path):
            with open(macro_path, 'r', encoding='utf-8') as f:
                macro_state = json.load(f)
            for row in macro_state.get("rows", []):
                if len(row) > 1:
                    candidates.append({"symbol": row[1]})
    except Exception as e:
        logger.error(f"[BG_ANALYST] Failed to read macro watchlist: {e}")

    reports_dir = os.path.join(os.getcwd(), 'data', 'reports')
    os.makedirs(reports_dir, exist_ok=True)
        
    symbols_to_process = []
    skipped_symbols = []
    added_trace = []
    skipped_trace = []
    for c in candidates:
        sym = c.get("symbol")
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
            if mtime.date() == datetime.now().date():
                needs_report = False
                
        if needs_report:
            symbols_to_process.append(sym)
            added_trace.append(f"   ➕ Added: **{sym}**")
        else:
            skipped_symbols.append(sym)
            skipped_trace.append(f"   ⏩ Skipped: **{sym}** (Cached Report Active)")
            
    # [NEW] Telemetry Write for List Building
    try:
        from src.config.vli import get_vli_path
        from datetime import datetime
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        trace_log = "\n".join(added_trace)
        if trace_log:
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp} 📋 **[ORCHESTRATOR]** Candidate Evaluation Trace:\n{trace_log}\n")
                tf.flush()
    except Exception as e:
        logger.error(f"Failed to write candidate trace: {e}")

    if symbols_to_process:
        logger.info(f"[BG_ANALYST] Missing/stale reports detected for: {symbols_to_process}. Beginning generation sequence.")
        
        try:
            from src.config.vli import get_vli_path
            telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp} 🤖 **[ORCHESTRATOR]** Background LLM Analyst initiated deep-scan for {len(symbols_to_process)} missing candidates.\n")
                tf.flush()
        except Exception:
            pass

        total = len(symbols_to_process)
        for i, sym in enumerate(symbols_to_process, 1):
            logger.info(f"[BG_ANALYST] Spawning background LangGraph for {sym}...")
            
            try:
                timestamp = datetime.now().strftime("[%H:%M:%S]")
                with open(telemetry_file, "a", encoding="utf-8") as tf:
                    tf.write(f"\\n{timestamp} 🔄 **[ANALYST]** Spawning deep-dive intelligence for **{sym}** ({i}/{total})...\\n")
                    tf.flush()
            except Exception:
                pass
            
            result_text, _ = await _invoke_vli_agent(f"analyze {sym}", thread_id=f"bg_{sym}")
            
            # [HARDENING] Only persist valid reports. Prevent caching of LLM errors.
            is_valid = True
            if not result_text or len(result_text) < 50:
                is_valid = False
            elif "Agent reasoning encountered a failure" in result_text or "timed out" in result_text.lower():
                is_valid = False
            
            if is_valid:
                try:
                    r_path = os.path.join(os.getcwd(), 'data', 'reports', f"analyze_{sym.lower()}.md")
                    os.makedirs(os.path.dirname(r_path), exist_ok=True)
                    generation_ts = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
                    header = f"> **Generated:** {generation_ts}\n\n"
                    with open(r_path, "w", encoding="utf-8") as rf:
                        rf.write(header + result_text)
                except Exception as e:
                    logger.error(f"[BG_ANALYST] Failed to save report for {sym}: {e}")
            else:
                logger.warning(f"[BG_ANALYST] Execution failed for {sym}. Artifact discarded to prevent cache poisoning.")
            
            try:
                timestamp = datetime.now().strftime("[%H:%M:%S]")
                with open(telemetry_file, "a", encoding="utf-8") as tf:
                    tf.write(f"\\n{timestamp} ✅ **[ANALYST]** Report generated for **{sym}** (Rate limit stagger: 30s).\\n")
                    tf.flush()
            except Exception:
                pass
            
            logger.info(f"[BG_ANALYST] Generated report for {sym}. Sleeping 30s to respect API rate limits.")
            await asyncio.sleep(30)
            
        try:
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\\n{timestamp} ✨ **[ORCHESTRATOR]** Background LLM Analyst sequence complete.\\n")
                tf.flush()
        except Exception:
            pass
            
        logger.info("[BG_ANALYST] Background generation sequence complete.")
            
    # [NEW] Automatically spawn Meta-Analysis if all reports are ready
    await run_meta_analysis(manual_trigger=False)

async def run_daily_morning_analysis():
    """
    Cron task running at 6:00 AM EDT. Pulls TV Sync and then triggers idle analysis.
    """
    global _is_morning_scan_running
    if _is_morning_scan_running:
        logger.warning("[BG_ANALYST] Morning Market Scan is already running. Ignoring duplicate trigger.")
        return

    _is_morning_scan_running = True
    logger.info("[BG_ANALYST] Triggering 6:00 AM Morning Market Scan.")
    try:
        from src.config.vli import get_vli_path
        from datetime import datetime
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        with open(telemetry_file, "a", encoding="utf-8") as tf:
            tf.write(f"\n{timestamp} 📡 **[ORCHESTRATOR]** Running Daily Scanner...\n")
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
        
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        
        scanner_bucket_path = os.path.join(VAULT_ROOT, "_cobalt", "01_Transit", "Buckets", "SCANNER_RES_state.json")
        if not os.path.exists(scanner_bucket_path):
            if manual_trigger: return "Error: SCANNER_RES_state.json not found."
            return
            
        with open(scanner_bucket_path, encoding="utf-8") as f:
            scanner_res_content = json.load(f)
            
        candidates = scanner_res_content.get("candidates", [])
        if not candidates:
            if manual_trigger: return "Error: No scanner candidates found."
            return
            
        reports_dir = os.path.join(os.getcwd(), 'data', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        # [NEW] Check if already generated today
        meta_path = os.path.join(reports_dir, "analyze_meta.md")
        if not manual_trigger and os.path.exists(meta_path):
            mtime = datetime.fromtimestamp(os.path.getmtime(meta_path))
            if mtime.date() == datetime.now().date():
                return
                
        compiled_reports = []
        missing_reports = []
        
        for c in candidates:
            sym = c.get("symbol")
            if not sym: continue
            
            r_path = os.path.join(reports_dir, f"analyze_{sym.lower()}.md")
            if os.path.exists(r_path):
                mtime = datetime.fromtimestamp(os.path.getmtime(r_path))
                if mtime.date() == datetime.now().date():
                    with open(r_path, "r", encoding="utf-8") as rf:
                        content = rf.read()
                        if len(content) > 100:
                            compiled_reports.append(f"### REPORT: {sym}\n{content}\n---\n")
                            continue
            missing_reports.append(sym)
            
        if missing_reports:
            logger.warning(f"[META_ANALYST] Missing valid reports for: {missing_reports}. Triggering background generation.")
            
            import asyncio
            # Trigger background generation
            asyncio.create_task(run_idle_analysis(manual_trigger=True))
            
            if manual_trigger:
                return f"Missing valid reports for {len(missing_reports)} candidates. Initiating background generation... You will be notified with a UX card when the Executive Briefing is ready."
            return
            
        # Write to telemetry
        try:
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp} 🧠 **[META_ANALYST]** Synthesizing Executive Morning Briefing from {len(compiled_reports)} reports...\n")
                tf.flush()
        except Exception:
            pass
            
        # Bundle for LLM
        bundle = "\n".join(compiled_reports)
        compiled_symbols = [c.get("symbol") for c in candidates if c.get("symbol")]
        source_str = f"Source Scans: {', '.join(compiled_symbols)}"
        
        prompt = (
            "You are the Chief Market Strategist for Blueshell Securities. "
            "Synthesize an 'Executive Morning Briefing' from the following institutional reports. "
            "Focus on: 1. Sector Concentration/Convergence, 2. Aggregate Risk Profile (Volatility/ATR), "
            "and 3. The absolute best 2 high-conviction setups of the day. "
            f"CRITICAL INSTRUCTION: You MUST include the exact following line at the end of your briefing to cite the source documents: '{source_str}'. "
            "Be concise, tactical, and highly professional.\n\n"
            f"{bundle}\n\n--FORCE-GRAPH"
        )
        
        result_text, _ = await _invoke_vli_agent(prompt, thread_id="bg_meta_analysis")
        
        if result_text and "Agent reasoning encountered a failure" not in result_text and "timed out" not in result_text.lower():
            meta_path = os.path.join(reports_dir, "analyze_meta.md")
            generation_ts = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
            header = f"> **Generated:** {generation_ts}\n\n"
            
            with open(meta_path, "w", encoding="utf-8") as mf:
                mf.write(header + result_text)
                
            logger.info("[META_ANALYST] Executive Morning Briefing completed and cached.")
            
            # [NEW] Push to Analysis Report Card
            global _vli_last_async_report
            _vli_last_async_report = header + result_text
            
            try:
                timestamp = datetime.now().strftime("[%H:%M:%S]")
                with open(telemetry_file, "a", encoding="utf-8") as tf:
                    tf.write(f"\n{timestamp} 🏆 **[META_ANALYST]** Executive Morning Briefing successfully compiled.\n")
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

@app.on_event("startup")
async def startup_event():
    logger.info("VLI_SYSTEM: API Server booting...")

    # [NEW] Dashboard Integrity Guard
    # Ensure backend_root is defined for the startup event
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
    cobalt_scheduler.add_timer(
        task_id="INBOX_WATCHER",
        name="VLI Inbox & Archiver Watcher",
        type="REPEAT",
        schedule=2,
        period_unit="seconds",
        priority="NORMAL",
        callback=vli_inbox_tick
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
        
        # Register Background Idle Analyst (Runs every 10 minutes)
        cobalt_scheduler.add_timer(
            task_id="IDLE_ANALYST",
            name="Background LLM Analyst Scanner",
            type="REPEAT",
            schedule=10,
            period_unit="minutes",
            priority="NORMAL",
            callback=run_idle_analysis
        )
        
        # Register 6:00 AM Full Generation Cron
        cobalt_scheduler.add_timer(
            task_id="DAILY_ANALYST",
            name="6:00 AM Morning Analyst Prep",
            type="CALENDAR",
            schedule="0 6 * * *",
            priority="HIGH",
            callback=run_daily_morning_analysis
        )
        logger.info("VLI_SYSTEM: Internal Cobalt scanner logic BYPASSED (Using TradingView Engine)")
    else:
        # Register Internal Cobalt Scanner Logic
        from src.tools.sortino_sniper_trawl import run_background_trawl, run_intraday_trawl
        
        cobalt_scheduler.add_timer(
            task_id="DAILY_COMBAT_TRAWL",
            name="Daily Combat List Update",
            type="CALENDAR",
            schedule="15 7 * * *",
            priority="HIGH",
            callback=run_background_trawl
        )
        
        cobalt_scheduler.add_timer(
            task_id="INTRADAY_COMBAT_TRAWL",
            name="Intraday Momentum Trawl Watchdog",
            type="REPEAT",
            schedule=60,
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

    cobalt_scheduler.add_timer(
        task_id="SMC_5M_POLLER",
        name="5-Minute Structure Alert Watchdog",
        type="REPEAT",
        schedule=5,
        period_unit="minutes",
        priority="NORMAL",
        callback=poll_5m_patterns
    )
    
    cobalt_scheduler.start()
    
    # Note: Macro Sync is now handled by the standalone vli_macro_worker.py process.


# Load examples into Milvus if configured
load_examples()

# Initialize research database
try:
    db_success = init_database()
    if db_success:
        logger.info("Research database initialized successfully")
    else:
        logger.warning("Research database initialization skipped - some features may be limited")
except Exception as e:
    logger.error(f"Failed to initialize research database: {e}")
    logger.warning("Continuing without database - some features may be limited")

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
    reporter_llm_type: str = "reasoning"
    vli_llm_type: str = "core"
    background_synthesis: bool = False
    thread_id: str | None = None
    snaptrade_settings: dict | None = None


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
                    
                # Dynamically enrich the has_report status for macro rows
                from datetime import datetime
                for row in macro_watchlist_content.get("rows", []):
                    if len(row) > 1:
                        sym = row[1]
                        sym_clean = sym.replace('^', '').replace('=', '').lower()
                        r_path1 = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{sym.lower()}.md')
                        r_path2 = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{sym_clean}.md')
                        has_report = os.path.exists(r_path1) or os.path.exists(r_path2)
                        
                        meta = {"has_report": has_report}
                        if has_report:
                            mtime = max(os.path.getmtime(r_path1) if os.path.exists(r_path1) else 0,
                                        os.path.getmtime(r_path2) if os.path.exists(r_path2) else 0)
                            meta["updated_at"] = datetime.fromtimestamp(mtime).isoformat()
                            
                        # Append the report status at the end of the row (or as the 7th element)
                        if len(row) == 6:
                            row.append(meta)
                        elif len(row) >= 7 and isinstance(row[-1], dict):
                            row[-1].update(meta)
                            
            except Exception as e:
                logger.error(f"Failed to read MACRO_WATCHLIST_state.json: {e}")
                
        # 6. Read SCANNER_RES state
        scanner_res_content = {}
        scanner_bucket_path = os.path.join(VAULT_ROOT, "_cobalt", "01_Transit", "Buckets", "SCANNER_RES_state.json")
        if os.path.exists(scanner_bucket_path):
            try:
                with open(scanner_bucket_path, encoding="utf-8") as f:
                    scanner_res_content = json.load(f)
                    
                # [NEW] Inject Shield Candidates from segregated pipeline
                shield_path = os.path.join(os.getcwd(), "data", "SHIELD_COMBAT_LIST.json")
                if os.path.exists(shield_path):
                    try:
                        with open(shield_path, encoding="utf-8") as sf:
                            s_data = json.load(sf)
                            s_list = s_data.get("combat_list", [])
                            for c in s_list:
                                c["tier"] = "SHIELD"
                            if "candidates" not in scanner_res_content:
                                scanner_res_content["candidates"] = []
                            scanner_res_content["candidates"].extend(s_list)
                    except Exception as e:
                        logger.error(f"Failed to inject shield data: {e}")
                    
                # Dynamically enrich the has_report status to ensure UI polling catches live background generation
                from datetime import datetime
                for key in ["candidates", "sword_candidates", "shield_candidates"]:
                    for cand in scanner_res_content.get(key, []):
                        sym = cand.get("symbol", "")
                        if sym:
                            r_path = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{sym.lower()}.md')
                            cand["has_report"] = False
                            if os.path.exists(r_path):
                                cand["has_report"] = True
                                mtime = os.path.getmtime(r_path)
                                report_dt = datetime.fromtimestamp(mtime).isoformat()
                                cand_dt = cand.get("updated_at", "")
                                if not cand_dt or report_dt > cand_dt:
                                    cand["updated_at"] = report_dt
                                
            except Exception as e:
                logger.error(f"Failed to read SCANNER_RES_state.json: {e}")

        logger.info(f"[VLI_TRACE] State compiled for return. Telemetry size: {len(telemetry_tail)} bytes.")
        
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content={
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
                "client_id_echo": client_id
            },
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
                tf.write(f"\n{timestamp} ### 🔄 [GLOBAL REFRESH] Target: ALL\n> Synchronizing all active Watchlist Engines...\n")
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
                tf.write(f"\n{timestamp} ### 🔄 [UX REFRESH] Target: {target}\n> Triggering forced update of Macro Watchlist Engine...\n")
                tf.flush()
            
            await get_macro_symbols.ainvoke({"fast_update": True})
            
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"> Macro Watchlist states securely synced to frontend payload.\n")
                tf.flush()
            return {"status": "success", "target": target}

            
        with open(telemetry_file, "a", encoding="utf-8") as tf:
            tf.write(f"\n{timestamp} ### ⚠️ [UX REFRESH ERROR]\n> Target generic card identifier `{target}` not securely mapped for forced refreshes.\n")    
            tf.flush()
        return {"status": "ignored", "target": target, "msg": "Card identifier not recognized."}
    except Exception as e:
        logger.error(f"Failed to refresh card {target}: {e}")
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        try:
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"\n{timestamp} ### ❌ [UX REFRESH FAILED]\n> Error resolving card '{target}': {e}\n")    
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
        from snaptrade_client import SnapTrade
        cid = os.getenv("SNAPTRADE_CLIENT_ID", "")
        ckey = os.getenv("SNAPTRADE_CONSUMER_KEY", "")
        uid = os.getenv("SNAPTRADE_USER_ID", "")
        usecret = os.getenv("SNAPTRADE_USER_SECRET", "")
        if not (cid and ckey and uid and usecret):
            return JSONResponse({"error": "Missing SnapTrade credentials"}, status_code=400)
            
        client = SnapTrade(client_id=cid, consumer_key=ckey)
        res = client.account_information.list_user_accounts(user_id=uid, user_secret=usecret)
        accounts = getattr(res, 'body', res)
        # Ensure it's JSON serializable
        if not isinstance(accounts, list):
            accounts = []
        parsed_accounts = []
        for a in accounts:
            if hasattr(a, 'to_dict'):
                parsed_accounts.append(a.to_dict())
            elif isinstance(a, dict):
                parsed_accounts.append(a)
        return JSONResponse({"accounts": parsed_accounts})
    except Exception as e:
        logger.error(f"SnapTrade accounts error: {e}")
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

@app.get("/api/brokerage/history")
async def get_brokerage_history(account_id: str, start_date: str, end_date: str):
    from fastapi.responses import JSONResponse
    try:
        from snaptrade_client import SnapTrade
        from src.services.brokerage_cache import BrokerageCache
        from datetime import datetime, timezone, timedelta
        
        cid = os.getenv("SNAPTRADE_CLIENT_ID", "")
        ckey = os.getenv("SNAPTRADE_CONSUMER_KEY", "")
        uid = os.getenv("SNAPTRADE_USER_ID", "")
        usecret = os.getenv("SNAPTRADE_USER_SECRET", "")
        if not (cid and ckey and uid and usecret):
            return JSONResponse({"error": "Missing SnapTrade credentials"}, status_code=400)
            
        client = SnapTrade(client_id=cid, consumer_key=ckey)
        
        # We always fetch the last 3 days to catch delayed overnight syncs from Fidelity.
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        fetch_start_str = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
        
        # Force a deeper fetch if the requested start_date is older than the oldest date in our cache
        cached_acts = BrokerageCache.get_activities(account_id)
        oldest_cached_date = today_str
        for act in cached_acts:
            placed_time = act.get('trade_date') or act.get('time_placed') or act.get('trade_time') or act.get('timestamp') or act.get('time') or act.get('date') or ''
            if placed_time:
                date_only = str(placed_time)[:10]
                if date_only < oldest_cached_date:
                    oldest_cached_date = date_only
                    
        if start_date < oldest_cached_date:
            fetch_start_str = start_date
            
        fetched_activities = []
        try:
            activities_res = client.transactions_and_reporting.get_activities(
                user_id=uid, 
                user_secret=usecret, 
                accounts=account_id, 
                start_date=fetch_start_str, 
                end_date=today_str
            )
            fetched_activities = getattr(activities_res, 'body', activities_res)
            if not isinstance(fetched_activities, list):
                fetched_activities = []
        except Exception as e:
            logger.warning(f"Initial fetch to SnapTrade raised exception (likely background sync timeout): {e}")
            fetched_activities = []
            
        # SnapTrade Background Sync Workaround:
        # If we asked for deep history and got nothing (or timed out), SnapTrade might be asynchronously syncing with Fidelity.
        # We poll a few times to give the background sync enough time to complete.
        is_deep_fetch = fetch_start_str < (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
        if not fetched_activities and is_deep_fetch:
            import asyncio
            for attempt in range(3):
                await asyncio.sleep(5)
                try:
                    activities_res2 = client.transactions_and_reporting.get_activities(
                        user_id=uid, user_secret=usecret, accounts=account_id, 
                        start_date=fetch_start_str, end_date=today_str
                    )
                    fetched_activities = getattr(activities_res2, 'body', activities_res2)
                    if not isinstance(fetched_activities, list):
                        fetched_activities = []
                    
                    if fetched_activities:
                        break # Successfully retrieved data, exit retry loop
                except Exception as e:
                    logger.error(f"Failed to fetch SnapTrade activities on retry {attempt+1}: {e}")
                    fetched_activities = []
            
        # Fetch live orders to catch today's executed trades before Fidelity's overnight batch settlement
        try:
            orders_res = client.account_information.get_user_account_orders(
                user_id=uid, user_secret=usecret, account_id=account_id, state="all"
            )
            orders = getattr(orders_res, 'body', orders_res)
            if isinstance(orders, list):
                for o in orders:
                    # Normalize Order schema to match Activity schema for the cache
                    if 'id' not in o and 'brokerage_order_id' in o:
                        o['id'] = str(o['brokerage_order_id'])
                    if 'type' not in o and 'action' in o:
                        o['type'] = str(o['action'])
                    if 'units' not in o and 'filled_quantity' in o:
                        o['units'] = float(o.get('filled_quantity', 0) or 0)
                    if 'price' not in o and 'execution_price' in o:
                        o['price'] = float(o.get('execution_price', 0) or 0)
                    if 'trade_date' not in o and 'time_placed' in o:
                        o['trade_date'] = str(o['time_placed'])
                fetched_activities.extend(orders)
        except Exception as e:
            logger.warning(f"Failed to fetch live orders: {e}")
            
        # Merge fetched activities into our durable cache
        activities = BrokerageCache.merge_activities(account_id, fetched_activities)
        
        # Reverse to oldest first for chronological timestamping
        activities_chronological = list(reversed(activities))
        
        daily_counters = {}
        results = []
        active_symbols = {}
        
        for act in activities_chronological:
            action = act.get('type', act.get('action', 'N/A')).upper()
            if action not in ["BUY", "SELL", "BOUGHT", "SOLD", "BTO", "STC", "BTC", "STO", "REINVEST", "DIVIDEND"]:
                continue
                
            # robust symbol extraction
            if isinstance(act.get('symbol'), dict):
                sym = act['symbol'].get('symbol', 'N/A')
            elif isinstance(act.get('universal_symbol'), dict):
                sym = act['universal_symbol'].get('symbol', act.get('symbol', 'N/A'))
            else:
                sym = act.get('symbol', 'N/A')
                
            if isinstance(sym, dict):
                sym = sym.get('symbol', 'N/A')
                
            if sym == 'N/A': continue
            sym_raw = str(sym).upper().replace('-USD', '').replace('*', '')
            if sym_raw == 'SPAXX': continue
            
            qty = float(act.get('units', 0))
            price = float(act.get('price', 0))
            
            if sym_raw not in active_symbols:
                active_symbols[sym_raw] = {"quantity": 0, "total_cost": 0, "average_cost": 0.0}
            
            if action in ["BUY", "BOUGHT", "BTO", "BTC", "REINVEST", "DIVIDEND"]:
                active_symbols[sym_raw]['quantity'] += qty
                active_symbols[sym_raw]['total_cost'] += qty * price
                if active_symbols[sym_raw]['quantity'] > 0:
                    active_symbols[sym_raw]['average_cost'] = active_symbols[sym_raw]['total_cost'] / active_symbols[sym_raw]['quantity']
            elif action in ["SELL", "SOLD", "STC", "STO"]:
                active_symbols[sym_raw]['quantity'] -= qty
                if active_symbols[sym_raw]['quantity'] <= 0.0001:
                    active_symbols[sym_raw]['quantity'] = 0
                    active_symbols[sym_raw]['total_cost'] = 0
                    active_symbols[sym_raw]['average_cost'] = 0
                else:
                    active_symbols[sym_raw]['total_cost'] = active_symbols[sym_raw]['quantity'] * active_symbols[sym_raw]['average_cost']

            # Extract real trade date for Order History log
            placed_time = act.get('trade_date') or act.get('time_placed') or act.get('trade_time') or act.get('timestamp') or act.get('time') or act.get('date') or ''
            date_only = str(placed_time)[:10] if placed_time else "Unknown"
            
            real_time = None
            placed_time_str = str(placed_time) if placed_time else ""
            if placed_time_str:
                if 'T' in placed_time_str:
                    real_time = placed_time_str.split('T')[1][:8]
                elif ' ' in placed_time_str:
                    real_time = placed_time_str.split(' ')[-1][:8]
                    
            # Check if it's a default SnapTrade midnight UTC/EDT time (which means no real execution time is known)
            if real_time and (real_time.startswith('00:00') or real_time.startswith('04:00') or real_time.startswith('05:00')):
                real_time = None
            
            if start_date <= date_only <= end_date or date_only == "Unknown":
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
                    "status": "Executed"
                })
        
        results.reverse() # Newest first for UI log
            
        open_positions = {s: d for s, d in active_symbols.items() if d['quantity'] > 0.0001}
        positions_payload = []
        
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
                
            try:
                data = yf.download(yf_tickers, period="5d", group_by='ticker', threads=True, progress=False)
                for yf_sym, sym in yf_to_raw.items():
                    pdata = open_positions[sym]
                    try:
                        sym_data = data if len(yf_tickers) == 1 else data[yf_sym]
                        last_price = safe_float(sym_data['Close'].iloc[-1])
                        prev_close = safe_float(sym_data['Close'].iloc[-2]) if len(sym_data) > 1 else last_price
                        
                        last_time_obj = sym_data.index[-1]
                        last_time_str = last_time_obj.strftime('%Y-%m-%d 16:00') if hasattr(last_time_obj, 'strftime') else 'Unknown'
                        
                        qty = safe_float(pdata['quantity'])
                        avg_cost = safe_float(pdata['average_cost'])
                        total_cost = safe_float(pdata['total_cost'])
                        current_value = qty * last_price
                        
                        todays_gl_dol = (last_price - prev_close) * qty
                        todays_gl_pct = ((last_price - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
                        
                        total_gl_dol = current_value - total_cost
                        total_gl_pct = (total_gl_dol / total_cost * 100) if total_cost > 0 else 0.0
                        
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
            
        return JSONResponse({"history": results, "positions": positions_payload})
    except Exception as e:
        logger.error(f"SnapTrade history error: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)


async def _invoke_vli_agent(
    text: str,
    image: str | None = None,
    direct_mode: bool = False,
    raw_data_mode: bool = False,
    reporter_llm_type: str = "reasoning",
    vli_llm_type: str = "reasoning",
    thread_id: str | None = None,
    snaptrade_settings: dict | None = None,
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

    # [FAST-PATH TRIGGERS] Deterministic bypass for low-latency situation awareness
    is_smc = "SMC" in text.upper()
    is_fast_override = any(kw in text.upper() for kw in ["FAST", "QUICK", "HIGH-LEVEL", "SHORTCUT", "RAPID"])

    # Exclusion: Technical keywords (Sortino, Sharpe, etc.) should use the full agent graph
    tech_keywords = ["SORTINO", "SHARPE", "RISK", "VOLATILITY", "ANALYSIS", "REPORT", "ANALYZE", "EXPLAIN"]
    is_technical = any(kw in text.upper() for kw in tech_keywords) and not (is_smc and is_fast_override)

    is_macro = "MACRO" in text.upper() and any(kw in text.upper() for kw in ["LIST", "PRICE", "SYMBOLS", "ENVIRONMENT"])
    is_price_list = ("SYMBOL" in text.upper() or "PORTFOLIO" in text.upper()) and "PRICE" in text.upper()
    is_vix = "VIX" in text.upper() and len(text) < 30

    # 2. Refined Ticker Query: Qualified vs Unqualified vs Analyze
    qualifiers = ["PRICE", "VOLUME", "OHLC", "VALUE", "MA", "RSI", "MACD"]
    is_qualified = any(q in text.upper() for q in qualifiers) or "GET " in text.upper() or len(text.split()) <= 2
    is_analyze = ("ANALYZE" in text.upper() or "ANALYSIS" in text.upper() or "SENTIMENT" in text.upper() or "NEWS" in text.upper()) and not (is_smc and is_fast_override)
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
    
    workflow_input = {
        "messages": [HumanMessage(content=content_obj)],
        "plan_iterations": 0,
        "steps_completed": 0,
        "final_report": "",
        "current_plan": None,
        "observations": [],
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

        # Run the graph and get the final state with an aggressive timeout (300s to respect AsyncRetries safely)
        final_state = await asyncio.wait_for(graph.ainvoke(workflow_input, config=workflow_config), timeout=300.0)

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
        logger.warning("VLI Agent: Master orchestration timed out (300s).")
        return "Agent processing timed out (300s).", {}
    except Exception as e:
        import traceback
        with open("C:\\github\\cobalt-multi-agent\\backend\\vli_error.txt", "w") as f:
            f.write(traceback.format_exc())
        logger.error(f"VLI Agent: Failed with error: {e}")
        return scrub_vli_output(f"Agent reasoning encountered a failure: {str(e)}"), {}


async def _background_synthesis_task(text: str, image: str | None, direct_mode: bool, reporter_llm_type: str, vli_llm_type: str, thread_id: str, silent: bool = False, snaptrade_settings: dict | None = None):
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
            _persist_vli_report(text, response_text)

    except Exception as e:
        logger.error(f"[ASYNC_SYNTHESIS] Background report failed: {e}")


@app.post("/api/vli/action-plan")
async def post_vli_action_plan(request: VLIActionPlanRequest, background_tasks: BackgroundTasks, client_id: str = Header("default", alias="X-VLI-Client-ID")):
    """Handle chat or action-plan updates from the VLI Sidebar."""
    try:
        from src.config.vli_context import vli_client_id
        vli_client_id.set(client_id)
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

    # [NEW] TV_SYNC Direct Control Interception
    import re
    command_text = request.text.strip().lower()
    
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

    # [NEW] Meta-Analysis Interception
    if request.text.strip().lower() == "run meta analysis":
        res_msg = await run_meta_analysis(manual_trigger=True)
        # Also persist this AI response to history so it shows up in the chat!
        _append_to_vli_history("ai", res_msg, thread_id=transaction_id)
        return {"response": res_msg, "status": "OK", "error_details": None, "thread_id": transaction_id}

    # [NEW] Meta-Analysis Eviction Interception
    req_lower = request.text.strip().lower()
    verbs = ["delete", "remove", "invalidate", "scrub"]
    targets = ["briefing", "daily briefing", "morning briefing"]
    
    if any(req_lower == f"{v} {t}" for v in verbs for t in targets):
        reports_dir = os.path.join(os.getcwd(), 'data', 'reports')
        meta_path = os.path.join(reports_dir, "analyze_meta.md")
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
            scanner_path = os.path.join(VAULT_ROOT, "_cobalt", "01_Transit", "Buckets", "SCANNER_RES_state.json")
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

    is_admin_cmd = any(word in clean_req_text for word in ["CLEAR", "PURGE", "RESET", "SCAN", "FORCE", "RESTART"])
    
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
    QUERY_TOKENS = ["WHY", "WHAT", "HOW", "WHEN", "WHERE", "WHO", "CAN", "SHOULD", "IS", "ARE", "DID", "DO", "DOES", "EXPLAIN", "COMPARE", "ANALYZE"]
    ADMIN_TOKENS = ["CLEAR", "RESET", "REBOOT", "START", "STOP", "PAUSE", "TOGGLE", "PURGE", "FLUSH", "RUN", "GENERATE"]
    
    first_word = cleaned_input.split()[0] if cleaned_input else ""
    
    global_intent = "COMMAND"
    if first_word in QUERY_TOKENS:
        global_intent = "QUERY"
    elif first_word in ADMIN_TOKENS:
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

        if ticker:
            try:
                from src.tools.finance import get_raw_smc_tables
                import asyncio

                report = await asyncio.wait_for(get_raw_smc_tables(ticker=ticker), timeout=25.0)

                # [FIX] Persist early for Async path so double-click works immediately
                clean_text = request.text.replace("--raw", "").replace("--RAW", "").strip()
                _persist_vli_report(clean_text, report)

                # Dispatch deep learning agent to background
                background_tasks.add_task(_background_synthesis_task, request.text, request.image, request.direct_mode, request.reporter_llm_type, request.vli_llm_type, transaction_id, False, request.snaptrade_settings)
                return {"response": report, "status": "ASYNC_PENDING", "error_details": None, "state": {}}
            except Exception as fe:
                logger.warning(f"VLI Async-Path: Atomic resolution failed for '{ticker}': {fe}")

    try:
        response_text, final_vli_state = await _invoke_vli_agent(request.text, request.image, request.direct_mode, request.raw_data_mode, request.reporter_llm_type, request.vli_llm_type, thread_id=transaction_id, snaptrade_settings=request.snaptrade_settings)
        
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

    return {"response": response_text, "status": "OK", "error_details": None, "thread_id": transaction_id}


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
                    f.write(f"\n{ts} 📡 **[BACKGROUND FETCH]** Raw news successfully gathered for {', '.join(targets)}. Sent to Analysis Window.\n")
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
        try:
            macro_path = os.path.join(VAULT_ROOT, "_cobalt", "01_Transit", "Buckets", "MACRO_WATCHLIST_state.json")
            if os.path.exists(macro_path):
                with open(macro_path, encoding="utf-8") as f:
                    macro_content = json.load(f)
                    for row in macro_content.get("rows", []):
                        if len(row) > 1 and row[1].upper() == sym:
                            in_watchlist = True
                            break
                            
            scanner_path = os.path.join(VAULT_ROOT, "_cobalt", "01_Transit", "Buckets", "SCANNER_RES_state.json")
            if not in_watchlist and os.path.exists(scanner_path):
                with open(scanner_path, encoding="utf-8") as f:
                    scanner_content = json.load(f)
                    for cand in scanner_content.get("candidates", []):
                        if cand.get("symbol", "").upper() == sym:
                            in_watchlist = True
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
                text=f"analyze {sym}",
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
    workflow_input = {
        "messages": messages,
        "plan_iterations": 0,
        "final_report": "",
        "current_plan": None,
        "observations": [],
        "auto_accepted_plan": auto_accepted_plan,
        "enable_background_investigation": enable_background_investigation,
        "research_topic": messages[-1]["content"] if messages else "",
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

    report_path = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{symbol.lower()}.md')
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"success": True, "content": content}
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


# Trigger Telemetry Purge on Server Startup
try:
    from src.config.vli import purge_stale_vli_sessions
    purge_stale_vli_sessions()
except Exception:
    pass

# Mount the backend directory to serve the dashboard HTML
backend_dir = os.path.dirname(os.path.abspath(__file__))  # src/server
backend_root = os.path.abspath(os.path.join(backend_dir, "..", ".."))  # backend/
public_dir = os.path.join(backend_root, "public")
app.mount("/", StaticFiles(directory=public_dir, html=True), name="static")

# Trigger hot reload
# RELOAD_FLAG_2026_04_20_12_56
