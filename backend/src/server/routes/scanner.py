from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import json
import logging
import asyncio
import aiohttp
import numpy as np
import pandas as pd
import traceback
import sys
from datetime import datetime
from typing import Dict, Any, List
from zoneinfo import ZoneInfo
from src.tools.finance import _fetch_batch_history, _extract_ticker_data

from src.tools.scanner import (
    _build_session_watchlist_impl, 
    _run_activity_pulse_impl,
    build_session_watchlist,
    run_activity_pulse
)
from src.tools.sortino_sniper_trawl import run_background_trawl
from src.tools.shield_scanner_trawl import run_shield_trawl

router = APIRouter()
logger = logging.getLogger(__name__)

def patch_json():
    """Global process-level patch for NumPy serialization in standard json library."""
    original_default = json.JSONEncoder.default
    def new_default(self, obj):
        if hasattr(obj, "item"):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return original_default(self, obj)
    json.JSONEncoder.default = new_default

patch_json()

def inject_watchdog():
    """Global watchdog to catch and trace JSON serialization failures to disk."""
    log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "SCANNER_TRACE.log"))
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    original_dumps = json.dumps
    def wrapped_dumps(obj, *args, **kwargs):
        try:
            return original_dumps(obj, *args, **kwargs)
        except TypeError as e:
            if "int64" in str(e) or "serializable" in str(e):
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("\n" + "!"*60 + "\n")
                    f.write(f"!!! WATCHDOG TRACE: JSON SERIALIZATION FAILURE !!!\n")
                    f.write(f"Time: {datetime.now().isoformat()}\n")
                    f.write(f"Error: {e}\n")
                    f.write(f"Context Class: {obj.__class__.__name__}\n")
                    f.write(f"Context Start: {str(obj)[:500]}\n")
                    f.write("\nStack Trace:\n")
                    f.write(traceback.format_exc())
                    f.write("!"*60 + "\n")
                logger.error(f"JSON Watchdog caught failure. Trace written to {log_path}")
            raise e
    json.dumps = wrapped_dumps
    
    original_dump = json.dump
    def wrapped_dump(obj, fp, *args, **kwargs):
        try:
            return original_dump(obj, fp, *args, **kwargs)
        except TypeError as e:
            if "int64" in str(e) or "serializable" in str(e):
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("\n" + "!"*60 + "\n")
                    f.write(f"!!! WATCHDOG TRACE: JSON FILE WRITE FAILURE !!!\n")
                    f.write(f"Time: {datetime.now().isoformat()}\n")
                    f.write(f"Error: {e}\n")
                    f.write("\nStack Trace:\n")
                    f.write(traceback.format_exc())
                    f.write("!"*60 + "\n")
                logger.error(f"JSON Watchdog caught file failure. Trace written to {log_path}")
            raise e
    json.dump = wrapped_dump

inject_watchdog()

def sanitize_data(data):
    """Hyper-aggressive recursive sanitizer for NumPy, Pandas, and Python structural types."""
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple, set)):
        return [sanitize_data(v) for v in data]
    elif isinstance(data, pd.Timestamp):
        return data.isoformat()
    elif isinstance(data, (pd.Series, pd.DataFrame)):
        return sanitize_data(data.to_dict())
    elif isinstance(data, np.ndarray):
        return data.tolist()
    elif hasattr(data, "item") and not isinstance(data, (type, pd.Series, pd.DataFrame)): 
        return data.item()
    return data

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "item"): # Standard NumPy scalar conversion
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)

@router.get("/trawl")
async def trigger_scanner_trawl():
    """Manual trigger for Layer A (The Background Trawl)."""
    try:
        results = await run_background_trawl()
        return sanitize_data({"status": "success", "data": results})
    except Exception as e:
        logger.error(f"Trawl failed: {e}")
        return {"status": "error", "message": str(e)}

import time

TRENDS_CACHE = {}  # {symbol: {"trends": {...}, "sparkline": [...], "timestamp": float}}
TRENDS_CACHE_EXPIRY = 300  # 5 minutes
PENDING_FETCH = set()

async def bulk_fetch_trends_and_sparklines(symbols):
    # Filter out symbols that are already being fetched
    to_fetch = [s for s in symbols if s not in PENDING_FETCH]
    if not to_fetch:
        return
        
    for s in to_fetch:
        PENDING_FETCH.add(s)
        
    try:
        import yfinance as yf
        from src.tools.macros import extract_single_ticker_df
        
        logger.info(f"VLI: Background fetching sparkline histories for: {to_fetch}")
        
        # Download in chunks of 30 to avoid rate limits
        chunk_size = 30
        for i in range(0, len(to_fetch), chunk_size):
            chunk = to_fetch[i:i+chunk_size]
            
            # Fetch ONLY the 15m timeframe for sparklines to minimize payload and yfinance connections
            c_batch_15m = await asyncio.to_thread(yf.download, chunk, period="1mo", interval="15m", progress=False)
            
            now = time.time()
            for sym in chunk:
                df_15m = extract_single_ticker_df(c_batch_15m, sym)
                
                sparkline = []
                if df_15m is not None and not df_15m.empty and "Close" in df_15m.columns:
                    try:
                        closes = df_15m["Close"].tail(30).tolist()
                        sparkline = [{"v": float(v)} for v in closes]
                    except Exception as spark_e:
                        logger.error(f"Failed to extract sparkline for {sym}: {spark_e}")
                        
                # Preserve existing trends, update sparkline
                cached = TRENDS_CACHE.get(sym)
                existing_trends = cached.get("trends") if cached else None
                
                TRENDS_CACHE[sym] = {
                    "trends": existing_trends or {},
                    "sparkline": sparkline,
                    "timestamp": now
                }
            
            # Yield control back to event loop
            await asyncio.sleep(0.3)
            
    except Exception as e:
        logger.error(f"Failed in background sparkline fetch: {e}")
    finally:
        for s in to_fetch:
            PENDING_FETCH.discard(s)

async def enrich_candidates_with_trends(candidates):
    if not candidates:
        return candidates
        
    now = time.time()
    symbols_to_fetch = []
    
    for c in candidates:
        sym = c.get("symbol")
        if not sym:
            continue
        # If candidate already contains valid pre-calculated trends and sparkline, populate cache and bypass fetch
        if "trends" in c and isinstance(c["trends"], dict) and len(c["trends"]) >= 5 and c.get("sparkline"):
            if sym not in TRENDS_CACHE:
                TRENDS_CACHE[sym] = {
                    "trends": c["trends"],
                    "sparkline": c["sparkline"],
                    "timestamp": now
                }
            
        cached = TRENDS_CACHE.get(sym)
        if not cached or (now - cached["timestamp"] > TRENDS_CACHE_EXPIRY) or not cached.get("sparkline"):
            if sym not in PENDING_FETCH and sym not in symbols_to_fetch:
                symbols_to_fetch.append(sym)
            
    if symbols_to_fetch:
        asyncio.create_task(bulk_fetch_trends_and_sparklines(symbols_to_fetch))
            
    # Populate the trends and sparklines from cache
    for c in candidates:
        sym = c.get("symbol")
        db_trends = c.get("trends", {})
        db_sparkline = c.get("sparkline", [])
        
        if sym in TRENDS_CACHE:
            cached_trends = TRENDS_CACHE[sym].get("trends")
            c["trends"] = cached_trends if (cached_trends and len(cached_trends) >= 5) else db_trends
            
            cached_spark = TRENDS_CACHE[sym].get("sparkline")
            c["sparkline"] = cached_spark if cached_spark else db_sparkline
        else:
            c["trends"] = db_trends
            c["sparkline"] = db_sparkline
            
    return candidates

@router.get("/bunker")
async def get_bunker_list():
    """Retrieve the current persistent Combat List (Phase A)."""
    strike_list_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "STRIKE_LIST.json"))
    if not os.path.exists(strike_list_path):
        return {"status": "success", "data": []}
    
    try:
        with open(strike_list_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            updated_at = data.get("updated_at", data.get("metadata", {}).get("last_sync", None))
            
            payload = {"status": "success"}
            if isinstance(data, list):
                candidates = data
            else:
                candidates = data.get("candidates", data.get("strike_list", []))
                
            # Enrich candidates with dynamic trend alignments
            enriched = await enrich_candidates_with_trends(candidates)
            payload["data"] = enriched
            
            if updated_at:
                payload["updated_at"] = updated_at
                
            return sanitize_data(payload)
    except Exception as e:
        logger.error(f"Failed to read bunker: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/shield-trawl")
async def trigger_shield_trawl():
    """Manual trigger for Layer A (The Defensive Background Trawl)."""
    try:
        results = await run_shield_trawl.ainvoke({})
        return sanitize_data({"status": "success", "data": results})
    except Exception as e:
        logger.error(f"Shield Trawl failed: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/shield-bunker")
async def get_shield_bunker_list():
    """Retrieve the current Shield Combat List."""
    strike_list_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "STRIKE_LIST.json"))
    if not os.path.exists(strike_list_path):
        return {"status": "success", "data": []}
    
    try:
        with open(strike_list_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return sanitize_data({"status": "success", "data": data})
            return sanitize_data({"status": "success", "data": data.get("candidates", data.get("strike_list", []))})
    except Exception as e:
        logger.error(f"Failed to read shield bunker: {e}")
        return {"status": "error", "message": str(e)}


async def fetch_av_gainers() -> List[Dict[str, Any]]:
    # Note: Function name kept as `fetch_av_gainers` to preserve downstream contracts, but now uses FMP
    import os
    import aiohttp
    
    api_key = os.getenv("FMP_API_KEY", "")
    endpoints = [
        f"https://financialmodelingprep.com/stable/biggest-gainers?apikey={api_key}",
        f"https://financialmodelingprep.com/stable/biggest-losers?apikey={api_key}",
        f"https://financialmodelingprep.com/stable/most-actives?apikey={api_key}"
    ]
    
    universe = []
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            for url in endpoints:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, list):
                            for item in data:
                                price = float(item.get("price", 0.0))
                                if price < 10.0:
                                    continue
                                    
                                universe.append({
                                    "symbol": item.get("symbol", ""),
                                    "price": price,
                                    "change": f"{item.get('changesPercentage', 0.0)}%",
                                    "volume": item.get("volume", 0)
                                })
        return universe
    except Exception as e:
        logger.error(f"Failed to fetch FMP market movers: {e}")
        
    return []

@router.get("/state")
async def get_scanner_state():
    """Silently bridges the 5-minute Intraday Pulse cache specifically for UI Auto-refreshing."""
    import os
    import json
    from src.config.vli import get_vli_path
    
    try:
        transit_path = get_vli_path(os.path.join("01_Transit", "Buckets", "STRIKE_RES_state.json"))
        if os.path.exists(transit_path):
            with open(transit_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
    except Exception as e:
        logger.error(f"[Scanner State API] Integrity fetch failed: {e}")
    return {"candidates": []}

@router.get("/stream")
async def scanner_stream():
    """Diagnostic endpoint to stream symbols progressively."""
    
    async def sse_generator():
        try:
            # Telemetry: Start
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'Initializing Phase 0: Fetching AV Top Gainers...'}), cls=NpEncoder)}\n\n"
            
            # 1. Load Universe (Combat List + Discovery)
            strike_list = []
            strike_list_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "STRIKE_LIST.json"))
            if os.path.exists(strike_list_path):
                try:
                    with open(strike_list_path, "r", encoding="utf-8") as f:
                        c_data = json.load(f)
                        strike_list = c_data.get("candidates", c_data.get("strike_list", []))
                        pulse_mode = c_data.get("pulse_mode", "")
                        yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Combat List loaded: {len(strike_list)} swords in the bunker.'}), cls=NpEncoder)}\n\n"
                except Exception as e:
                    logger.warning(f"Failed to load combat list: {e}")
                    pulse_mode = ""

            if "TradingView" in pulse_mode:
                discovery_raw = []
                yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'TradingView High-Fidelity Mode detected. Skipping Alpha Vantage Top Movers.'}), cls=NpEncoder)}\n\n"
            else:
                discovery_raw = await fetch_av_gainers()
                if not discovery_raw:
                     discovery_raw = [{"symbol": t, "price": 15.0, "change": "5%", "volume": 1000000} for t in ["CELH", "SYM", "IOT", "MDB", "CRWD", "RBLX"]]
            
            # Merge: Combat List results are enriched with discovery data if they overlap, 
            # or we add discovery candidates to the tail.
            phase0_symbols = {c["symbol"]: c for c in strike_list}
            for d in discovery_raw:
                if d["symbol"] not in phase0_symbols:
                    phase0_symbols[d["symbol"]] = d
            
            # Discard stocks less than $1 and zeroed out entries
            phase0_raw = sanitize_data([
                {**r, "price": float(r.get("price", 0) or 0), "symbol": str(r.get("symbol", ""))}
                for r in phase0_symbols.values() 
                if float(r.get("price", 0) or 0) >= 1.0 and r.get("symbol")
            ])
            
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Universe finalized: {len(phase0_raw)} symbols. Calculating Sortino...'}), cls=NpEncoder)}\n\n"
            
            # [NEW] Calculate Sortino for Phase 0 Universe with normalization
            from src.tools.scanner import batch_fetch_sortino
            # Normalize: discard .A, .PRO, etc for yfinance
            all_symbols = [r["symbol"] for r in phase0_raw if r["symbol"]]
            normalized_map = {s: s.split(".")[0].split("-")[0] for s in all_symbols}
            search_symbols = list(set(normalized_map.values()))
            
            # Safety check: if too many symbols, yfinance might hang. We log this.
            if len(search_symbols) > 50:
                yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'High-density universe detected ({len(search_symbols)}). Phase 0 might take up to 30s...'}), cls=NpEncoder)}\n\n"

            sortino_map_norm = await batch_fetch_sortino(search_symbols)
            
            for r in phase0_raw:
                norm_s = normalized_map.get(r["symbol"])
                r["sortino"] = sortino_map_norm.get(norm_s, 0.0)

            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Fetching 5-day Sparkline data for {len(search_symbols)} symbols...'}), cls=NpEncoder)}\n\n"
            try:
                NY_TZ = ZoneInfo("America/New_York")
                sparkline_data = await asyncio.to_thread(_fetch_batch_history, search_symbols, "5d", "1h")
                for r in phase0_raw:
                    norm_s = normalized_map.get(r["symbol"])
                    sparkline = []
                    if norm_s:
                        try:
                            ticker_spark_df = _extract_ticker_data(sparkline_data, norm_s)
                            if not ticker_spark_df.empty:
                                ticker_spark_df = ticker_spark_df.sort_index()
                                last_10 = ticker_spark_df.tail(10)
                                for _, row in last_10.iterrows():
                                    ts = row.name
                                    if ts.tzinfo is None:
                                        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
                                    sparkline.append({"v": float(row["Close"]), "t": ts.astimezone(NY_TZ).strftime(" %m/%d  %I:%M %p").lower()})
                        except Exception as e:
                            logger.error(f"Sparkline error for {norm_s}: {e}")
                    r["sparkline"] = sparkline
            except Exception as e:
                logger.error(f"Sparkline batch fetch failed: {e}")
                for r in phase0_raw:
                    if "sparkline" not in r:
                        r["sparkline"] = []

            
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Sortino calculations complete for {len(phase0_raw)} symbols.'}), cls=NpEncoder)}\n\n"

            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'payload': phase0_raw[:5], 'msg': 'Phase 0 completed successfully.'}), cls=NpEncoder)}\n\n"
            # Intermediate UI grid rendering disabled: Wait for full pipeline completion.
            symbols = [r["symbol"] for r in phase0_raw if r["symbol"]]
            universe_csv = ",".join(symbols)
            
            # 2. Phase 1
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'Initiating Phase 1: Applying Sortino static filters...'}), cls=NpEncoder)}\n\n"
            
            if "TradingView" in pulse_mode:
                yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'TradingView High-Fidelity Mode active. Bypassing Phase 1 LLM filters to preserve raw strategy candidates...'}), cls=NpEncoder)}\n\n"
                p1_symbols = symbols
                p1_details = [{"symbol": s, "grade": "A", "sortino": next((x.get("sortino", 0.0) for x in phase0_raw if x["symbol"] == s), 0.0)} for s in symbols]
            else:
                try:
                    if os.environ.get("BYPASS_REASONING_MODEL", "false").lower() == "true":
                        yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'BYPASS MODE ENABLED'}), cls=NpEncoder)}\n\n"
                        yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'THINKING: OFF'}), cls=NpEncoder)}\n\n"
                    p1_res_str = await _build_session_watchlist_impl(strategy_config="{}", universe_csv=universe_csv)
                    p1_data = json.loads(p1_res_str)
                    p1_symbols = p1_data.get("watchlist", [])
                    p1_details = p1_data.get("detail", [])
                    
                    # Re-inject SHIELD/SWORD/SNIPER candidates to bypass Phase 1 small-cap fundamental filters
                    for s in symbols:
                        match = next((x for x in phase0_raw if x["symbol"] == s), {})
                        if match.get("tier") in ["SHIELD", "SWORD", "SNIPER"] and s not in p1_symbols:
                            p1_symbols.append(s)
                            if not any(d["symbol"] == s for d in p1_details):
                                p1_details.append({"symbol": s, "grade": match.get("grade", "B"), "sortino": match.get("sortino", 0.0)})
                    
                    
                    # Report details including rejects
                    for d in p1_details:
                        if d["grade"] in ["C", "F"]:
                            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'REJECTED: {d["symbol"]} - Grade {d["grade"]} (Sortino: {d.get("sortino", 0.0)})'}), cls=NpEncoder)}\n\n"
                        else:
                            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'PASSED: {d["symbol"]} - Grade {d["grade"]} (Sortino: {d.get("sortino", 0.0)})'}), cls=NpEncoder)}\n\n"
                    
                    yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Phase 1 complete. Surviving Candidates: {len(p1_symbols)}'}), cls=NpEncoder)}\n\n"
                except Exception as e:
                    logger.error(f"Phase 1 error: {e}")
                    p1_symbols = []
                    yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Phase 1 failed: {str(e)}'}), cls=NpEncoder)}\n\n"
                
            p1_full = sanitize_data([])
            for s in p1_symbols:
                # Attach the grade and sortino from Phase 1 details
                detail = next((d for d in p1_details if d["symbol"] == s), {"grade": "B", "sortino": 0.0})
                match = next((x for x in phase0_raw if x["symbol"] == s), {"symbol": s, "price": 0, "change": "0%", "volume": 0})
                p1_full.append(sanitize_data({**match, "grade": detail["grade"], "sortino": detail.get("sortino", 0.0)}))
                
            # Intermediate UI grid rendering disabled: Wait for full pipeline completion.

            # 3. Phase 2
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'Initiating Phase 2: Analyzing Pulse & RVOL...'}), cls=NpEncoder)}\n\n"
            if not p1_symbols:
                yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'Phase 2 skipped: Empty input from Phase 1.'}), cls=NpEncoder)}\n\n"
                yield f"data: {json.dumps(sanitize_data({'type': 'phase2', 'data': []}), cls=NpEncoder)}\n\n"
            else:
                try:
                    # Invoke actual Phase 2 logic
                    if os.environ.get("BYPASS_REASONING_MODEL", "false").lower() == "true":
                        yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'BYPASS MODE ENABLED'}), cls=NpEncoder)}\n\n"
                        yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'THINKING: OFF'}), cls=NpEncoder)}\n\n"
                    p2_res_str = await _run_activity_pulse_impl(strategy_config="{}", watchlist=json.dumps(p1_symbols, cls=NpEncoder))
                    p2_data = json.loads(p2_res_str)
                    p2_candidates = p2_data.get("candidates", [])
                    p2_misses = p2_data.get("misses", [])
                    
                    for m in p2_misses:
                        sym = m.get("symbol", "UNKNOWN")
                        rvol = m.get("rvol", 0.0)
                        yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'PULSE REJECTED: {sym} - RVOL: {rvol:.2f}'}), cls=NpEncoder)}\n\n"
                    
                    yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Phase 2 complete. Diagnostic Candidates Displayed: {len(p2_candidates)}'}), cls=NpEncoder)}\n\n"
                except Exception as e:
                    logger.error(f"Phase 2 error: {e}")
                    p2_candidates = []
                    tb_str = traceback.format_exc()
                    yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'Phase 2 failed: {str(e)} | Trace: {tb_str}'}), cls=NpEncoder)}\n\n"
                    
                p2_full = []
                for p in p2_candidates:
                    match = next((x for x in phase0_raw if x["symbol"] == p["symbol"]), {})
                    merged = sanitize_data({**match, **p})
                    
                    # Preserve origin tier to ensure UI filtering by SHIELD/SWORD/SNIPER doesn't break
                    if "tier" in match and match["tier"] in ["SHIELD", "SWORD", "SNIPER"]:
                        merged["tier"] = match["tier"]
                        
                    p2_full.append(merged)
                
                # Compute multi-timeframe trends for sniper candidates
                if p2_full:
                    p2_full = await enrich_candidates_with_trends(p2_full)
                    
                yield f"data: {json.dumps(sanitize_data({'type': 'phase2', 'data': p2_full}), cls=NpEncoder)}\n\n"

                
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': 'Pipeline execution finished cleanly.'}), cls=NpEncoder)}\n\n"
        except Exception as outer_e:
            logger.error(f"Scanner Generator CRITICAL FAILURE: {outer_e}")
            yield f"data: {json.dumps(sanitize_data({'type': 'telemetry', 'msg': f'PIPELINE CRITICAL ERROR: {str(outer_e)}'}), cls=NpEncoder)}\n\n"
        
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@router.delete("/purge")
async def purge_scanner_cache():
    """Purges the entire scanner combat list and transit state cache."""
    try:
        from src.tools.scanner import clear_scanner_cache
        res = await clear_scanner_cache.ainvoke({})
        return {"status": "success", "message": res}
    except Exception as e:
        logger.error(f"Failed to purge scanner cache: {e}")
        return {"status": "error", "message": str(e)}
