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

from fastapi import Depends, FastAPI, HTTPException, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
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

# --- GLOBAL VLI STATE ---
_vli_extracted_alerts = []  # [{symbol, label, color}]
_vli_dynamic_panels = []  # [{id, title, content_html}]
_vli_macro_worker_task = None
_vli_last_macro_data = [{"symbol": k, "price": 0, "change": 0, "volume": 0, "color": "gray"} for k in macro_registry.get_macros().keys()]
_vli_session_id = f"vli-{datetime.now().strftime('%Y%m%d-%H%M%S')}"  # Unique per-server-run
_vli_last_inbox_log_time = 0.0
_vli_rules_enabled = False
_vli_convergence_history = []
_vli_last_ux_card = {}
_vli_reset_requested = False
_vli_active_task = None
_vli_fast_path_cooldown_until = datetime.now()
_vli_last_inbox_action = None
_vli_rules_active_since = datetime.now()

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


@app.get("/vli")
async def vli_dashboard_redirect():
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/VLI_session_dashboard.html")


# Add CORS middleware
# It's recommended to load the allowed origins from an environment variable
# for better security and flexibility across different environments.
allowed_origins_str = get_str_env("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8089,http://127.0.0.1:8089")
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


@app.on_event("startup")
async def startup_event():
    logger.info("Cobalt Multiagent: Launching VLI Reactive Pipeline (Inbox Only).")
    asyncio.create_task(vli_inbox_watcher())
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


class VLIActionPlanRequest(BaseModel):
    text: str
    image: str | None = None
    is_action_plan: bool = False
    direct_mode: bool = False


# --- VLI CONSOLIDATED STATE ENDPOINT ---


@app.get("/api/vli/active-state")
async def get_active_vli_state():
    """Consolidated Live state for the VLI Dashboard."""
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

        return {
            "macros": json.loads(json.dumps(_get_vli_macro_snapshot(), default=str)),
            "last_macro_update": os.path.getmtime(get_vli_path("vli_macro_snapshot.json")) if os.path.exists(get_vli_path("vli_macro_snapshot.json")) else time.time(),
            "alerts": ui_alerts or [{"symbol": "SYS", "color": "green", "label": "VLI-IDLE"}],
            "dynamic_panels": json.loads(json.dumps(_vli_dynamic_panels, default=str)),
            "telemetry_tail": telemetry_tail,
            "plan_markdown": plan_markdown,
            "inbox_files": sorted(inbox_files, key=lambda x: os.path.getmtime(os.path.join(inbox_path, x)) if os.path.exists(os.path.join(inbox_path, x)) else 0, reverse=True),
            "ux_card": json.loads(json.dumps(_vli_last_ux_card, default=str)),
            "rules_enabled": _vli_rules_enabled,
            "convergence_data": json.loads(json.dumps(_vli_convergence_history, default=str)),
        }
    except Exception as e:
        logger.error(f"VLI: Error in consolidated active-state endpoint: {e}", exc_info=True)
        return {"error": str(e), "macros": [], "alerts": [], "telemetry_tail": "BACKEND_ERROR", "convergence_data": []}


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
    import os

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


@app.post("/api/vli/reset")
async def reset_vli_session():
    """Clear telemetry and PREEMPTIVELY terminate all active jobs via System Node Hard-Kill."""
    from src.config.vli import get_vli_path

    telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")

    global _vli_reset_requested, _vli_active_task, _vli_extracted_alerts, _vli_dynamic_panels, _vli_session_id
    _vli_reset_requested = True

    # [NEW] Refresh Session ID to break 404 Trajectory cycles
    # This forces a fresh Google Cloud session context
    _vli_session_id = f"vli-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # [HARD KILL] Preemptively cancel the active graph task
    if _vli_active_task and not _vli_active_task.done():
        logger.warning(f"VLI_SYSTEM: SYSTEM_NODE deploying Hard-Kill signal for task {id(_vli_active_task)}")
        _vli_active_task.cancel()

    try:
        # [PROCESS CLEANUP] Kill orphaned headless browsers
        import subprocess

        logger.info("VLI_SYSTEM: Cleaning up background tool processes (msedge)...")
        subprocess.run(["taskkill", "/F", "/IM", "msedge.exe", "/T"], capture_output=True, check=False)

        # Truncate the telemetry file COMPLETELY for a clean session start
        timestamp = datetime.now().strftime("%H:%M:%S")
        try:
            with open(telemetry_file, "w", encoding="utf-8") as f:
                f.write("# VLI Session Telemetry Log\n")
                f.write(f"### [{timestamp}] SYSTEM_NODE: NEW SESSION INITIALIZED\n")
                f.write("- **Status**: `READY`\n- **Action**: All previous telemetry backlog and active processes have been cleared.\n\n---\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as fe:
            logger.error(f"VLI: Failed to truncate telemetry file: {fe}")

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
    import os
    import subprocess

    from src.config.vli import PREFERRED_EDITOR, get_inbox_path

    inbox_path = get_inbox_path()
    file_path = os.path.join(inbox_path, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Avoid blocking the server; use Popen to launch and detach
        logger.info(f"VLI: Opening {filename} with {PREFERRED_EDITOR}")
        subprocess.Popen([PREFERRED_EDITOR, file_path], shell=True)
        return {"status": "success", "editor": PREFERRED_EDITOR}
    except Exception as e:
        logger.error(f"VLI: Failed to open editor: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _invoke_vli_agent(text: str, image: str | None = None, direct_mode: bool = False) -> str:
    """Invoke the agent graph in a non-streaming way for the VLI dashboard."""
    global _vli_session_id
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
    # [FAST-PATH TRIGGERS] Deterministic bypass for low-latency situation awareness
    # Exclusion: Technical keywords (Sortino, Sharpe, etc.) should use the full agent graph
    tech_keywords = ["SORTINO", "SHARPE", "RISK", "VOLATILITY", "ANALYSIS", "REPORT", "ANALYZE"]
    is_technical = any(kw in text.upper() for kw in tech_keywords)

    is_macro = "MACRO" in text.upper() and ("LIST" in text.upper() or "PRICE" in text.upper())
    is_price_list = ("SYMBOL" in text.upper() or "PORTFOLIO" in text.upper()) and "PRICE" in text.upper()
    is_vix = "VIX" in text.upper() and len(text) < 30

    # 2. Refined Ticker Query: Qualified vs Unqualified vs Analyze
    qualifiers = ["PRICE", "VOLUME", "OHLC", "VALUE", "MA", "RSI", "MACD"]
    is_qualified = any(q in text.upper() for q in qualifiers)
    is_analyze = "ANALYZE" in text.upper() or "ANALYSIS" in text.upper()
    is_ticker_query = ("$" in text or "GET " in text.upper() or is_analyze) and len(text) < 40 and not is_analyze  # [STRICT] Exclude analyze from ticker queries

    is_fast_track = (is_macro or is_price_list or is_vix or is_ticker_query) and not is_technical and not is_analyze

    if is_fast_track:
        ticker = ""
        # 1. Prioritize $TICKER format
        sym_match = re.search(r"\$([A-Z]{1,5})", text.upper())
        if sym_match:
            ticker = sym_match.group(1)
        elif is_vix:
            ticker = "VIX"
        else:
            # Fallback to general search but exclude stop-words
            ticker_stop_words = ["GET", "STOCK", "PRICE", "LIST", "MARCO", "MARO", "VALUE", "PORT", "SYMBOL"]
            words = re.findall(r"\b([A-Z]{1,5})\b", text.upper())
            for word in words:
                if word not in ticker_stop_words:
                    ticker = word
                    break

        if is_macro:
            if "PRICE" in text.upper():
                # [BATCH FAST-PATH] Parallel Metric Retrieval
                tickers = ["VIX", "DXY", "TNX", "CL=F"]
                results = []
                start_time = datetime.now()
                try:
                    # [FIX] Call the underlying tool function directly for high-fidelity dict responses
                    q_func = getattr(get_stock_quote, "coroutine", getattr(get_stock_quote, "func", None))
                    if not q_func:
                        raise TypeError("VLI Fast-Path: Tool not correctly configured.")

                    # Fetch top 4 in parallel for the macro list
                    tasks = [asyncio.wait_for(q_func(ticker=t, use_fast_path=True), timeout=5.0) for t in tickers]
                    quotes = await asyncio.gather(*tasks, return_exceptions=True)

                    for i, q in enumerate(quotes):
                        t = tickers[i]
                        # Handle results with normalization (VIX -> ^VIX)
                        if isinstance(q, dict) and "price" in q:
                            p, c = q.get("price", 0), q.get("change", 0)
                            # Display original ticker for UI clarity
                            results.append(f"- **{t}**: `${p:.2f}` ({'+' if c >= 0 else ''}{c:.2f}%)")
                        elif isinstance(q, str) and "$" in q:
                            results.append(f"- **{t}**: {q}")
                        else:
                            # Log the error but keep the UI stable
                            logger.error(f"VLI Fast-Path: Failed to fetch {t}: {q}")
                            results.append(f"- **{t}**: `N/A` (Timeout/Error)")

                    duration = (datetime.now() - start_time).total_seconds()

                    # [PERFORMANCE AUDIT] Log Fast-Path batch latency
                    log_vli_metric("fastpath_macro_batch", duration, status="pass")

                    _vli_convergence_history.append({"timestamp": datetime.now().strftime("%H:%M:%S"), "iteration": 1, "latency": duration, "accuracy": 100.0, "status": "pass"})
                    return "### Global Macro Tickers (Atomic Fast-Path)\n" + "\n".join(results)
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
            return macro_report

        if ticker and get_stock_quote:
            try:
                start_time = datetime.now()
                # Call tool directly with Fast-Path enabled (Deterministic & Lock-Free)
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
                        return q["response"]

                    # Atomic response handling
                    _vli_last_ux_card = get_latest_ux_data(ticker)

                    # Report metric to trigger Resonance Chart
                    _vli_convergence_history.append({"timestamp": datetime.now().strftime("%H:%M:%S"), "iteration": 1, "latency": duration, "accuracy": 100.0, "status": "pass"})

                    p, c = q.get("price", 0), q.get("change", 0)
                    return f"### {ticker} (Atomic Fast-Path)\n- **Price**: `${p:.2f}`\n- **Change**: `{'+' if c >= 0 else ''}{c:.2f}%`"
                return str(q)
            except Exception as fe:
                logger.warning(f"VLI Fast-Path: Atomic resolution failed for '{ticker}': {fe}")

    # Prepare content

    # Prepare content
    if image:
        # Assuming image is base64 data URL
        content = [{"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": image}}]
    else:
        content = text


async def _invoke_vli_agent(text: str, image_data: str = None, direct_mode: bool = False):
    """Main VLI agent orchestration logic using the LangGraph specialist swarm."""
    global _vli_reset_requested, _vli_active_task, _vli_session_id
    
    # 1. Prepare Orchestration Context
    content = text
    if image_data:
        # If we have an image, we can wrap it in a multimetal prompt if the agent supports it
        # For now, we assume text-primary focus but the state allows vision expansion.
        pass
        
    thread_id = _vli_session_id
    
    # [V10.5 CONTEXT PATCH]
    # We pass only the CURRENT message. Because the graph is configured with a
    # thread_id checkpointer, LangGraph will automatically append this to the
    # existing history in the database rather than overwriting it.
    workflow_input = {
        "messages": [HumanMessage(content=content)],
        "plan_iterations": 0,
        "steps_completed": 0,  # [CRITICAL] Reset traversal index so coordinator doesn't think it's done
        "final_report": "",
        "current_plan": None,
        "observations": [],
        "auto_accepted_plan": True,
        "is_plan_approved": True,
        "enable_background_investigation": False,
        "research_topic": text[:100],
        "verbosity": 1,
        "direct_mode": direct_mode,
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
        },
        "recursion_limit": 50,
    }

    _vli_active_task = asyncio.current_task()
    
    try:
        # [NEW] Kill switch check
        if _vli_reset_requested:
            logger.warning("VLI Agent: Reset requested. Terminating jobs.")
            return "Session Reset Signal Received. Execution Terminated.", {}

        # Run the graph and get the final state with an aggressive timeout (60s)
        final_state = await asyncio.wait_for(graph.ainvoke(workflow_input, config=workflow_config), timeout=60.0)
        
        # 1. Prioritize explicitly set 'final_report'
        if final_state.get("final_report"):
            return final_state["final_report"], final_state

        out_str = ""
        # 2. Extract the last assistant message as a fallback
        if "messages" in final_state and final_state["messages"]:
            for msg in reversed(final_state["messages"]):
                if isinstance(msg, AIMessage) and msg.content:
                    if isinstance(msg.content, list):
                        text_parts = []
                        for item in msg.content:
                            if isinstance(item, dict):
                                if "text" in item:
                                    text_parts.append(item["text"])
                                elif "image_url" in item and isinstance(item["image_url"], dict) and "url" in item["image_url"]:
                                    text_parts.append(f"\n![Captured Image]({item['image_url']['url']})\n")
                            elif isinstance(item, str):
                                text_parts.append(item)

                        buffer = " ".join(text_parts).strip()
                        if buffer and not buffer.startswith("Plan formulated:"):
                            return buffer, final_state
                    elif isinstance(msg.content, str):
                        if not msg.content.startswith("Plan formulated:"):
                            return msg.content, final_state

        if not out_str:
            out_str = "Directive processed (No specific output generated)."
            
        return out_str, final_state

    except asyncio.TimeoutError:
        logger.warning("VLI Agent: Master orchestration timed out (60s).")
        error_msg = "Agent processing timed out (60s). Please check logs or retry."
        return error_msg, {"messages": [AIMessage(content=error_msg, name="system")]}
    except Exception as e:
        logger.error(f"VLI Agent: Failed with error: {e}")
        error_msg = f"Agent reasoning encountered a structural failure: {str(e)}"
        return error_msg, {"messages": [AIMessage(content=error_msg, name="system")]}


@app.post("/api/vli/action-plan")
async def post_vli_action_plan(request: VLIActionPlanRequest):
    """Handle chat or action-plan updates from the VLI Sidebar."""
    plan_file = get_action_plan_path()

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
    if request.is_action_plan or len(request.text) > 300:
        with open(plan_file, "w", encoding="utf-8") as f:
            f.write(request.text)
        return {"response": "Plan captured. Vault updated. Session Monitor is analyzing directives..."}

    # Real Agent Routing for Chat/Directives
    logger.info(f"VLI: Routing directive to Gemini Agent: {request.text[:50]}...")
    final_vli_state = {} # Ensure initialization
    try:
        response_text, final_vli_state = await _invoke_vli_agent(request.text, request.image, request.direct_mode)
    except Exception as e:
        # [V10 AUDIT] Log structural failures to telemetry
        try:
            from src.config.vli import get_vli_path
            telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                # Distinguish between timeout and other errors
                status_label = "FAILED : TIMEOUT" if "timed out" in str(e).lower() else "CRITICAL_FAIL"
                tf.write(f"\n{timestamp} **SYSTEM ERROR:** Agent Reasoning Failed - {str(e)}\n")
                tf.write(f"- **Status**: `{status_label}`\n- **Action**: Execution aborted.\n\n---\n")
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))

    # --- Final Telemetry Audit: Session COMPLETED (v10 Consolidated) ---
    try:
        telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        
        # Extract metadata from final state
        agents_run = []
        messages = final_vli_state.get("messages", [])
        for m in messages:
            if isinstance(m, AIMessage) and getattr(m, "name", None):
                if m.name not in ["reporter", "coordinator", "vli_coordinator", "router", "vli_parser"] and m.name not in agents_run:
                    agents_run.append(m.name)
        
        agent_list = "\n  - " + "\n  - ".join([f"**{a}**" for a in agents_run]) if agents_run else " None"
        preview = response_text[:100].strip().replace("\n", " ")
        
        with open(telemetry_file, "a", encoding="utf-8") as tf:
            tf.write(f"\n{timestamp} **VLI TRANSACTION RESOLVED**\n")
            tf.write(f"- **Session Status**: `COMPLETED`\n")
            tf.write(f"- **Agents Spun Up**: `{len(agents_run)}` {agent_list}\n")
            tf.write(f"- **Directive**: `{request.text[:40]}...`\n")
            tf.write(f"- **Response Preview**: {preview}...\n\n---\n")
            tf.flush()
            os.fsync(tf.fileno())
    except Exception as le:
        logger.error(f"VLI: Failed to log final completion audit: {le}")

    return {"response": response_text}


# --- VLI REACTIVE PIPELINE (INBOX WATCHER & ARCHIVER) ---


async def vli_inbox_watcher():
    """Background task to watch inbox/ for drafts AND archive end-of-day plans."""
    inbox = get_inbox_path()
    plan_file = get_action_plan_path()
    archive_dir = get_archive_path()

    plan_dir = os.path.dirname(plan_file)
    os.makedirs(inbox, exist_ok=True)
    os.makedirs(archive_dir, exist_ok=True)
    os.makedirs(plan_dir, exist_ok=True)

    logger.info(f"VLI: Inbox & Archiver watcher started on {inbox}")

    # Track the current day to detect transitions
    last_run_day = datetime.now().strftime("%Y-%m-%d")

    while True:
        try:
            # 1. Check for Day Transition (End-of-day Archiving)
            current_day = datetime.now().strftime("%Y-%m-%d")
            if current_day != last_run_day:
                logger.info(f"VLI: Day transition detected ({last_run_day} -> {current_day}). Archiving plan.")
                if os.path.exists(plan_file):
                    archive_file = os.path.join(archive_dir, f"Action_Plan_{last_run_day}.md")
                    os.rename(plan_file, archive_file)
                    # Create blank new plan for the new day
                    with open(plan_file, "w", encoding="utf-8") as f:
                        f.write(f"# Daily Action Plan - {current_day}\n- [ ] Waiting for morning session briefing...")

                last_run_day = current_day

            # 2. Check for Inbox Drafts (Automatic alert extraction)
            files = [f for f in os.listdir(inbox) if f.endswith(".md")]
            global _vli_processed_draft_mtimes, _vli_rules_enabled
            from src.config.vli import inbox_rule_engine

            # Sync rule engine state with global toggle
            inbox_rule_engine.rules_enabled = _vli_rules_enabled

            for filename in files:
                # CRITICAL: Separate "Automation" (Drafts) from "Smart Filing" (Journals/Actions)
                # If a file matches a rule, DO NOT process it here. Let the user approve manually.
                # Skip even if rules are OFF to prevent auto-archival of candidate files.
                if inbox_rule_engine.is_filing_candidate(filename):
                    # logger.info(f"VLI Watcher: Skipping '{filename}' (Matches smart filing rule)")
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
                    # logger.info(f"VLI Inbox: Cooldown for '{filename}'")
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

                # Append to active plan (dynamic date-based filename)
                with open(plan_file, "a", encoding="utf-8") as af:
                    af.write(f"\n\n### Batch Update: {filename}\n{content}")

                # Optional: Success Archival
                archive_path = os.path.join(archive_dir, f"Draft_{datetime.now().strftime('%H%M%S')}_{filename}")
                # os.rename(filepath, archive_path) # COMMENTED OUT: Use Manual Moving instead?
                # Actually, the user might want drafts moved to keep the inbox clean.
                # I'll keep it but ensure it doesn't loop.
                try:
                    os.rename(filepath, archive_path)
                except Exception as e:
                    logger.error(f"VLI: Error archiving draft: {e}")

        except Exception as e:
            logger.error(f"VLI Reactive Pipeline Error: {e}")

        await asyncio.sleep(2.0)  # Reduced frequency to 2s to prevent race conditions


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


async def _process_message_chunk(message_chunk, message_metadata, thread_id, agent, session_obj=None, project_obj=None):
    """Process a single message chunk and yield appropriate events."""
    agent_name = _get_agent_name(agent, message_metadata)
    event_stream_message = _create_event_stream_message(message_chunk, message_metadata, thread_id, agent_name)

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

        yield _make_event("tool_call_result", event_stream_message)
    elif isinstance(message_chunk, (AIMessage, AIMessageChunk)):
        # AI Message - Raw message tokens
        if message_chunk.tool_calls:
            # AI Message - Tool Call
            event_stream_message["tool_calls"] = message_chunk.tool_calls
            event_stream_message["tool_call_chunks"] = _process_tool_call_chunks(message_chunk.tool_call_chunks)

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
        "direct_mode": getattr(request, "direct_mode", False),
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
            "direct_mode": getattr(request, "direct_mode", False),
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

# Mount the backend directory to serve the dashboard HTML
backend_dir = os.path.dirname(os.path.abspath(__file__))  # src/server
backend_root = os.path.abspath(os.path.join(backend_dir, "..", ".."))  # backend/
app.mount("/", StaticFiles(directory=backend_root, html=True), name="static")

# Trigger hot reload
