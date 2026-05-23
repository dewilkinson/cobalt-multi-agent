# Agent: Analyst - Smart Money Concepts and advanced structure analysis.
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

import asyncio
import logging
import json
from typing import Any
from datetime import datetime

import pandas as pd
from langchain_core.tools import tool

from .finance import (
    _fetch_stock_history, 
    _normalize_ticker, 
    _extract_ticker_data, 
    _get_yf_semaphore, 
    _get_ttl_seconds,
    _fetch_replay_history
)
from .shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT
from src.services.datastore import DatastoreManager
from src.utils.temporal import get_effective_now

logger = logging.getLogger(__name__)

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context: Persistent, shared by Analyst sub-modules
_SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


@tool
async def run_smc_analysis(ticker: str, interval: str = "auto") -> str:
    """
    SMC Specialist Primitive: Executes a professional ICT-based analysis using Multi-Timeframe Alignment
    by default (interval='auto'). If a specific interval is provided (e.g. '1h'), it will execute a
    single-pass isolated scanner.
    """
    try:
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            from smartmoneyconcepts import smc
    except ImportError:
        return "[ERROR]: The 'smartmoneyconcepts' library is required. Run 'pip install smartmoneyconcepts'."

    norm_ticker = _normalize_ticker(ticker)
    
    # Check Artifact Cache
    entry = DatastoreManager.get_artifact(norm_ticker, "smc_analysis", interval)
    if entry:
        logger.info(f"[ANALYSIS_CACHE HIT] Reusing cached SMC analyst report for {norm_ticker}")
        return entry["data"]

    from src.config.smc_loader import load_smc_config
    config = load_smc_config()
    strategy = config.get("smc_strategy", {})

    # ==========================================
    # FALLBACK: Isolated Single-Pass Execution
    # ==========================================
    if interval.lower() != "auto":
        interval_norm = interval.lower()
        if interval_norm in ["1m", "2m", "5m", "15m"]:
            swing_length, period_needed = 20, "10d"
        elif interval_norm in ["1h", "4h", "2h"]:
            swing_length, period_needed = 10, "1mo"
        elif interval_norm in ["1d", "1wk"]:
            swing_length, period_needed = 5, "1y"
        else:
            swing_length, period_needed = 10, "1mo"

        history_samples = max(swing_length * 3, 100)
        logger.info(f"VLI SMC Analyst [CUSTOM OVERRIDE]: Executing {ticker} @ {interval}")

        try:
            ref_time = get_effective_now()
            is_replay = (ref_time.date() < datetime.now().date())
            
            if is_replay:
                data = await asyncio.wait_for(asyncio.to_thread(_fetch_replay_history, [norm_ticker], period_needed, interval, end_date=ref_time), timeout=15.0)
            else:
                data = await asyncio.wait_for(asyncio.to_thread(_fetch_stock_history, norm_ticker, period_needed, interval), timeout=15.0)
            
            if data.empty or len(data) < 10:
                return f"### {ticker} Analysis @ {interval}\n- [ERROR]: Insufficient data."

            df = data.tail(history_samples).copy()
            df.columns = [c.lower() for c in df.columns]

            # Use Adjusted Data for Structural Detection
            df_calc = df.copy()
            if "adj close" in df.columns:
                mask = df["close"] > 0
                df_calc.loc[mask, "adj_ratio"] = df["adj close"] / df["close"]
                df_calc.loc[~mask, "adj_ratio"] = 1.0
                for col in ["open", "high", "low", "close"]:
                    df_calc[col] = df[col] * df_calc["adj_ratio"]
            
            swings = smc.swing_highs_lows(df_calc, swing_length=swing_length)
            fvg = smc.fvg(df_calc)
            ob = smc.ob(df_calc, swings)
            structure = smc.bos_choch(df_calc, swings)

            fvg_count = len(fvg[fvg["FVG"].fillna(0) != 0]) if "FVG" in fvg.columns else 0
            ob_count = len(ob[ob["OB"].fillna(0) != 0]) if "OB" in ob.columns else 0

            report = [f"## Custom Single-Pass SMC Analysis: {ticker} ({interval})", ""]
            last = df.iloc[-1]
            report.append(f"- **OHLC**: O: `{last['open']:.2f}` | H: `{last['high']:.2f}` | L: `{last['low']:.2f}` | C: `{last['close']:.2f}` | V: `{last['volume']}`")

            last_struct = structure.iloc[-1]
            if last_struct.get("CHOCH") or last_struct.get("choch"):
                report.append("- **State**:  **Change of Character (ChoCh)** detected.")
            elif last_struct.get("BOS") or last_struct.get("bos"):
                report.append("- **State**:  **Break of Structure (BOS)** confirmed.")
            else:
                report.append("- **State**:  Stable market structure.")

            report.append(f"- **Order Blocks**: {ob_count} mapped.")
            active_obs = ob[ob["OB"].fillna(0) != 0] if "OB" in ob.columns else pd.DataFrame()
            if not active_obs.empty:
                ob_details = [f"  - {'Bullish' if r['OB'] == 1 else 'Bearish'}: `{r['Bottom']:.4f}` - `{r['Top']:.4f}`" for _, r in active_obs.tail(3).iterrows()]
                report.append(f"- **Key Order Blocks**:\n" + "\n".join(ob_details))

            report.append(f"- **FVGs**: {fvg_count} mapped.")
            active_fvgs = fvg[fvg["FVG"].fillna(0) != 0] if "FVG" in fvg.columns else pd.DataFrame()
            if not active_fvgs.empty:
                fvg_details = [f"  - {'Bullish' if r['FVG'] == 1 else 'Bearish'}: `{r['Bottom']:.4f}` - `{r['Top']:.4f}`" for _, r in active_fvgs.tail(3).iterrows()]
                report.append(f"- **Relevant FVGs**:\n" + "\n".join(fvg_details))
            report.append(f"\n**Current Price**: `${df['close'].iloc[-1]:.2f}`")
            
            final_report = "\n".join([str(r) for r in report])
            DatastoreManager.store_artifact(norm_ticker, "smc_analysis", interval, final_report, price=float(df['close'].iloc[-1]))
            return final_report
        except Exception as e:
            return f"[ERROR]: Single-pass failed: {e}"

    # ==========================================
    # APEX 500 AUTONOMOUS MTF SCANNER
    # ==========================================
    logger.info(f"VLI SMC Analyst [MTF AUTONOMOUS SCAN]: Executing Apex 500 Alignment for {ticker}")
    report = [f"## MTF SMC Alignment Scan: {ticker} (Apex 500 Scanner)", ""]

    macro_bias = "Neutral"
    macro_cfg = strategy.get("macro_map", {})
    tactical_cfg = strategy.get("tactical_map", {})
    trigger_cfg = strategy.get("execution_trigger", {})

    macro_lookback = macro_cfg.get("lookback_bars", 200)
    tactical_lookback = tactical_cfg.get("lookback_bars", 100)
    trigger_lookback = trigger_cfg.get("execution_lookback", 50)

    # [REPLAY_INSTRUMENTATION] Era-Detection & Adaptive Scaling
    ref_time = get_effective_now()
    is_deep_history = (datetime.now() - ref_time).days > 700
    
    if is_deep_history:
        logger.info(f"VLI_REPLAY: Entering Deep History Structural Mode (Origin: {ref_time})")
        macro_tf_actual, macro_period = "1mo", "10y"
        tactical_tf_actual, tactical_period = "1wk", "2y"
        trigger_tf_actual, trigger_period = "1d", "1y"
        report[0] = f"## MTF SMC Structural Replay: {ticker} (Legacy Analysis Mode)"
        report.append("> [!NOTE]\n> Intraday tactical data is substituted with Weekly/Daily structural pivots due to historical sampling limits (>2 years).")
    else:
        macro_tf_actual = macro_cfg.get("timeframes", ["1d"])[0]
        macro_period = "1y" if macro_tf_actual in ("1d", "4h") else "6mo"
        tactical_tf_actual = tactical_cfg.get("timeframes", ["1h"])[0]
        tactical_period = "1mo"
        trigger_tf_actual = trigger_cfg.get("timeframes", ["5m"])[0]
        trigger_period = "5d"

    # CONCURRENT FETCH
    async def fetch_with_sem(period, tf):
        async with _get_yf_semaphore():
            try:
                return await asyncio.wait_for(asyncio.to_thread(_fetch_stock_history, norm_ticker, period, tf), timeout=20.0)
            except (asyncio.TimeoutError, Exception) as e:
                if tf == "5m":
                    logger.warning(f"VLI_STABILITY: 5m fetch failed for {norm_ticker} ({e}). Falling back to 15m.")
                    try:
                        return await asyncio.wait_for(asyncio.to_thread(_fetch_stock_history, norm_ticker, period, "15m"), timeout=15.0)
                    except: pass
                raise e

    results = await asyncio.gather(
        fetch_with_sem(macro_period, macro_tf_actual), 
        fetch_with_sem(tactical_period, tactical_tf_actual), 
        fetch_with_sem(trigger_period, trigger_tf_actual), 
        return_exceptions=True
    )
    mData_res, tData_res, trData_res = results

    try:
        # 1. Macro Map
        if isinstance(mData_res, Exception): raise mData_res
        mDF = mData_res.tail(macro_lookback).copy()
        m_struct_detail = ""
        if not mDF.empty:
            mDF.columns = [c.lower() for c in mDF.columns]
            mSwings = smc.swing_highs_lows(mDF, swing_length=5)
            mStruct = smc.bos_choch(mDF, mSwings)
            lb = mStruct[mStruct["BOS"].fillna(0) != 0].tail(1)
            lc = mStruct[mStruct["CHOCH"].fillna(0) != 0].tail(1)
            if not lc.empty:
                macro_bias = "Bullish" if lc["CHOCH"].iloc[-1] == 1 else "Bearish"
                m_level = lc["Level"].iloc[-1] if "Level" in lc.columns else 0
                m_struct_detail = f" (CHoCH at `{m_level:.4f}`)"
            elif not lb.empty:
                macro_bias = "Bullish" if lb["BOS"].iloc[-1] == 1 else "Bearish"
                m_level = lb["Level"].iloc[-1] if "Level" in lb.columns else 0
                m_struct_detail = f" (BOS at `{m_level:.4f}`)"

        report.append(f"### 1. Macro Map ({macro_tf_actual})")
        report.append(f"- **Institutional Trend**: {macro_bias}{m_struct_detail}")

        # 2. Tactical Map
        tactical_ready = False
        if isinstance(tData_res, Exception): raise tData_res
        tDF = tData_res.tail(tactical_lookback).copy()
        if not tDF.empty:
            tDF.columns = [c.lower() for c in tDF.columns]
            tSwings = smc.swing_highs_lows(tDF, swing_length=10)
            tOB = smc.ob(tDF, tSwings)
            tFVG = smc.fvg(tDF)
            ob_c = len(tOB[tOB["OB"].fillna(0) != 0])
            fvg_c = len(tFVG[tFVG["FVG"].fillna(0) != 0])
            tactical_ready = ob_c > 0 or fvg_c > 0
            report.append(f"### 2. Tactical Map ({tactical_tf_actual})")
            report.append(f"- **Zones Mapped**: {ob_c} Order Blocks | {fvg_c} Fair Value Gaps.")
            
            active_obs = tOB[tOB["OB"].fillna(0) != 0]
            if not active_obs.empty:
                ob_details = [f"  - {'Bullish' if r['OB'] == 1 else 'Bearish'}: `{r['Bottom']:.4f}` - `{r['Top']:.4f}`" for _, r in active_obs.tail(3).iterrows()]
                report.append(f"- **Key Order Blocks**:\n" + "\n".join(ob_details))

            active_fvgs = tFVG[tFVG["FVG"].fillna(0) != 0]
            if not active_fvgs.empty:
                fvg_details = [f"  - {'Bullish' if r['FVG'] == 1 else 'Bearish'}: `{r['Bottom']:.4f}` - `{r['Top']:.4f}`" for _, r in active_fvgs.tail(3).iterrows()]
                report.append(f"- **Relevant FVGs**:\n" + "\n".join(fvg_details))

        # 3. Execution Trigger
        sweep_aligned = False
        if isinstance(trData_res, Exception): raise trData_res
        trDF = trData_res.tail(trigger_lookback).copy()
        if not trDF.empty:
            trDF.columns = [c.lower() for c in trDF.columns]
            trSwings = smc.swing_highs_lows(trDF, swing_length=5)
            trLiq = smc.liquidity(trDF, trSwings)
            liq_event = trLiq[trLiq["Liquidity"].fillna(0) != 0].tail(1)
            if not liq_event.empty:
                sweep_dir = "Bullish" if liq_event["Liquidity"].iloc[-1] == 1 else "Bearish"
                if sweep_dir == macro_bias: sweep_aligned = True
                report.append(f"### 3. Execution Trigger ({trigger_tf_actual})")
                report.append(f"- **Liquidity Sweep**: YES ({sweep_dir}) at `{liq_event['Level'].iloc[-1]:.4f}`")
            else:
                report.append(f"### 3. Execution Trigger ({trigger_tf_actual})")
                report.append("- **Liquidity Sweep**: NO (Accumulating)")

        # 4. Authorization Matrix
        report.append("### 4. Apex Authorization Matrix")
        status = "**[PASS]**" if macro_bias == "Bullish" and tactical_ready else "**[FAIL]**"
        report.append(f"- **Status**: {status} Execution trigger aligns with MTF Institutional Macro trend.")

        final_report = "\n".join([str(r) for r in report])
        curr_p = float(mDF.iloc[-1]["close"]) if not mDF.empty else 0.0
        DatastoreManager.store_artifact(norm_ticker, "smc_analysis", interval, final_report, price=curr_p if curr_p > 0 else None)
        return final_report
    except Exception as e:
        return f"[ERROR]: MTF Scanner failed: {e}"


@tool
async def get_raw_smc_tables(ticker: str, interval: str = "1d", period: str = "1y") -> str:
    """
    Headless Data Engine - Raw Data Tables Override
    Bypasses text synthesis and returns pure computational pandas structures as JSON.
    """
    try:
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            from smartmoneyconcepts import smc
    except ImportError:
        return json.dumps([{"error": "Library required"}])

    norm_ticker = ticker.upper()
    
    try:
        data = await asyncio.wait_for(asyncio.to_thread(_fetch_stock_history, norm_ticker, period, interval), timeout=15.0)
        df = data.tail(100).copy()
        if df.empty:
            return json.dumps([{"error": "No data"}])

        df.columns = [c.lower() for c in df.columns]
        swings = smc.swing_highs_lows(df, swing_length=15)
        structure = smc.bos_choch(df, swings)
        
        df["swing"] = swings["HighLow"] if "HighLow" in swings else None
        df["bos"] = structure["BOS"] if "BOS" in structure else None
        df["choch"] = structure["CHOCH"] if "CHOCH" in structure else None

        export_df = df.tail(20).copy().reset_index()
        for col in export_df.columns:
            if pd.api.types.is_datetime64_any_dtype(export_df[col]):
                export_df[col] = export_df[col].dt.strftime("%Y-%m-%d %H:%M:%S")

        final_json = json.dumps({
            "ticker": norm_ticker, 
            "type": "RAW_SMC_PRICE_ACTION_TABLE", 
            "timeframe": interval, 
            "data": json.loads(export_df.fillna("None").to_json(orient="records"))
        })

        DatastoreManager.store_artifact(norm_ticker, "smc_analysis", interval + "_raw", final_json, price=float(df["close"].iloc[-1]))
        
        # [CONTEXT CACHING] Upload massive raw payload to Gemini cache to save input tokens
        from src.llms.cache_manager import GeminiCacheManager
        cache_name = GeminiCacheManager.create_session_cache(
            model_name="gemini-1.5-flash", # Always fallback to flash for caching
            system_instruction="You are analyzing raw SMC financial tables. Extract exact structural data as requested.",
            large_payload=final_json,
            ttl_mins=15,
            key=f"smc_raw_{norm_ticker}_{interval}"
        )
        
        if cache_name:
            return f"[CACHED_PAYLOAD: {cache_name}]\nThe raw JSON data has been successfully securely cached in Gemini. You have full access to it."
        
        return final_json
    except Exception as e:
        return json.dumps([{"error": str(e)}])

# Backward Compatibility Alias
get_smc_analysis = run_smc_analysis

@tool
async def get_batch_smc_analysis(tickers_list: str) -> str:
    """
    SMC Specialist Primitive: Executes high-concurrency batch analysis for multiple tickers simultaneously.
    tickers_list: Comma-separated list of tickers (e.g., "SPY, QQQ, AAPL").
    Returns a unified, synthesized report of the macro structure for all tickers.
    """
    import asyncio
    
    tickers = [t.strip().upper() for t in tickers_list.split(",") if t.strip()]
    if not tickers:
        return "[ERROR] No valid tickers provided for batch analysis."
        
    if len(tickers) > 10:
        tickers = tickers[:10] # Hard bound to prevent runaway LLM tool calls
        
    # Bound concurrency to prevent slamming yfinance or local memory limits
    sem = asyncio.Semaphore(3)
    
    async def _safe_run(t: str):
        async with sem:
            try:
                # Direct ainvoke on the tool primitive
                res = await run_smc_analysis.ainvoke({"ticker": t, "interval": "auto"})
                return f"## {t} SMC Analysis\n{res}\n"
            except Exception as e:
                logger.error(f"[BATCH_SMC] Error analyzing {t}: {e}")
                return f"## {t} SMC Analysis\n[ERROR] Analysis failed: {str(e)}\n"
                
    logger.info(f"[BATCH_SMC] Starting concurrent analysis for {len(tickers)} assets: {tickers}")
    tasks = [_safe_run(t) for t in tickers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    final_out = []
    for t, res in zip(tickers, results):
        if isinstance(res, Exception):
            final_out.append(f"## {t} SMC Analysis\n[ERROR] Task crashed catastrophically: {str(res)}\n")
        else:
            final_out.append(res)
            
    final_report = "# Global Batch SMC Sweep\n\n" + "\n---\n".join(final_out)
    return final_report

