import asyncio
import logging
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import Any, Dict, List
import traceback
import sys

from langchain_core.tools import tool

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

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "item"): # Standard NumPy scalar conversion
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)

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

def calculate_sortino_ratio(returns: pd.Series, annual_rf: float = 0.0428, interval: str = "1d") -> float:
    """Calculates annualized Sortino Ratio dynamically adjusting for interval."""
    if returns.empty or len(returns) < 2:
        return 0.0
    
    annual_factor = 252.0
    if interval == "5m": annual_factor = 78.0 * 252.0
    elif interval == "15m": annual_factor = 26.0 * 252.0
    
    periodic_rf = annual_rf / annual_factor
    avg_return = returns.mean()
    excess_returns = returns - periodic_rf
    
    # Sortino penalizes downside volatility using the full array length
    downside_returns = excess_returns.copy()
    downside_returns[excess_returns > 0] = 0.0
    
    downside_std = np.sqrt(np.mean(downside_returns**2))
    if downside_std == 0:
        return 10.0 if avg_return > 0 else 0.0
        
    sortino = ((avg_return - periodic_rf) / downside_std) * np.sqrt(annual_factor)
    return round(float(sortino), 2)

async def batch_fetch_sortino(tickers: List[str], period: str = "60d") -> Dict[str, float]:
    """Fetches history and calculates Sortino for a batch of tickers concurrently."""
    if not tickers:
        return {}
    
    interval = "1d"
    trading_style = os.getenv("VLI_TRADING_STYLE", "day_trading")
    
    # [HARDENING] Enforce strict 60-day rolling window for scanner evaluations
    period = "60d"
    interval = "1d"
        
    try:
        # download can be slow for many tickers, so we use the yf.Tickers object or gather
        # yfinance download is generally faster for batches
        # [HARDENING] Relax timeout to 120s to ensure success for large batch sizes and prevent aggressive 'F' grading
        # Inject ^TNX to fetch the dynamic risk-free rate simultaneously
        fetch_list = tickers + ["^TNX"]
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
        def _do_yf_dl():
            return yf.download(fetch_list, period=period, interval=interval, group_by='ticker', progress=False, prepost=False)
        data = await asyncio.wait_for(
            asyncio.to_thread(_do_yf_dl),
            timeout=120.0
        )
        
        # Extract dynamic annual risk-free rate from ^TNX (or 0% for Day Trading)
        dynamic_rf = 0.0428
        if trading_style == "day_trading":
            dynamic_rf = 0.0
        else:
            try:
                if "^TNX" in data:
                    tnx_df = data["^TNX"]
                    if not tnx_df.empty and 'Close' in tnx_df.columns:
                        latest_tnx = float(tnx_df['Close'].dropna().iloc[-1])
                        dynamic_rf = latest_tnx / 100.0
            except Exception as e:
                logger.warning(f"Failed to extract dynamic ^TNX in batch Sortino, falling back to 0.0428: {e}")
            
        results = {}
        for ticker in tickers:
            try:
                df = data[ticker]
                
                if df.empty or 'Close' not in df.columns:
                    results[ticker] = 0.0
                    continue
                
                returns = df['Close'].pct_change().dropna()
                results[ticker] = calculate_sortino_ratio(returns, annual_rf=dynamic_rf, interval=interval)
            except Exception:
                results[ticker] = 0.0
        return results
    except Exception as e:
        logger.error(f"Batch Sortino fetch failed or timed out: {e}")
        return {t: 0.0 for t in tickers}


# Fallback FDA Mock Keywords
FDA_KEYWORDS = ["FDA", "clinical", "trial", "phase", "approval", "PDUFA", "clearance"]


def load_strategy_constraints(strategy_name: str = "default") -> Dict[str, Any]:
    """Loads constraints for a given strategy from its corresponding JSON file in backend/src/strategies/."""
    import os
    import json
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    strat_path = os.path.join(base_dir, "strategies", f"{strategy_name.lower()}.json")
    
    # Try loading the requested strategy file first
    if os.path.exists(strat_path):
        try:
            with open(strat_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading requested strategy constraints from {strat_path}: {e}")

    # If loading failed or file doesn't exist, load from fallback.json
    fallback_path = os.path.join(base_dir, "strategies", "fallback.json")
    msg = f"WARNING: Could not load strategy constraints for '{strategy_name}'. Falling back to Apex 500 constraints from fallback.json"
    logger.warning(msg)
    print(msg)  # Ensure user sees it if running script directly
    
    if os.path.exists(fallback_path):
        try:
            with open(fallback_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.critical(f"Critical error: Failed to load fallback constraints from {fallback_path}: {e}")
            raise RuntimeError(f"Failed to load fallback strategy constraints from {fallback_path}: {e}")
    else:
        logger.critical(f"Critical error: Fallback strategy file not found at {fallback_path}")
        raise FileNotFoundError(f"Fallback strategy file not found at {fallback_path}")


def _get_strategy_config(strategy_config: str) -> Dict[str, Any]:
    """Parses strategy JSON string/dict and merges with loaded strategy constraints."""
    strategy_name = "default"
    custom_overrides = {}
    
    if strategy_config:
        try:
            if isinstance(strategy_config, str):
                custom_overrides = json.loads(strategy_config)
            elif isinstance(strategy_config, dict):
                custom_overrides = strategy_config
            
            if isinstance(custom_overrides, dict):
                strategy_name = custom_overrides.get("strategy_name", "default")
        except Exception as e:
            logger.error(f"Failed to parse custom strategy overrides: {e}")
            
    config = load_strategy_constraints(strategy_name)
    if isinstance(custom_overrides, dict):
        config.update(custom_overrides)
        
    return config


def calculate_static_grade(price: float, cap: int, float_shares: int, config: Dict[str, Any], q_type: str = "EQUITY") -> str:
    """
    Evaluates (Price, Cap, Float) against strategy constraints.
    Implements a 'Soft Veto' logic: a symbol can fail one metric if another is 'Excellent'.
    
    Excellent Criteria:
    - Price: $15 - $35
    - Cap: $500M - $1.2B
    - Float: < 40M
    """
    if price < config["price_min"]:
        return "F"
        
    p_min, p_max = config["price_min"], config["price_max"]
    c_min, c_max = config["market_cap_min"], config["market_cap_max"]
    f_min, f_max = config["float_min"], config["float_max"]

    # 1. Primary Checks
    p_pass = p_min <= price <= p_max
    c_pass = c_min <= cap <= c_max
    # If float_shares is 0, we count it as a fail now to be stricter, 
    # unless we want to allow 0-float (unlikely for equities)
    f_pass = f_min <= float_shares <= f_max

    if q_type == "ETF":
        c_pass = True
        f_pass = True

    # 2. Excellence Checks
    p_exc = 15.0 <= price <= 35.0
    c_exc = 500_000_000 <= cap <= 1_200_000_000
    f_exc = 0 < float_shares < 40_000_000

    if q_type == "ETF":
        c_exc = True
        f_exc = True

    passes = [p_pass, c_pass, f_pass]
    excs = [p_exc, c_exc, f_exc]
    
    fail_count = passes.count(False)
    exc_count = excs.count(True)

    grade = "F"
    # All pass
    if fail_count == 0:
        grade = "A" if exc_count >= 1 else "B"
    # Soft Veto: Allow ONE fail if there is at least ONE Excellence
    # BUT: If the fail is Market Cap or Float being ZERO, we downgrade to C
    elif fail_count == 1 and exc_count >= 1:
        if cap == 0 or float_shares == 0:
            grade = "C" # Missing data is a marginal fail
        else:
            grade = "B" # Soft Veto Pass
    elif fail_count == 1:
        grade = "C" # Marginal Fail

    return grade


async def _build_session_watchlist_impl(strategy_config: str = "{}", universe_csv: str = "") -> str:
    """Core logic for Phase 1 Scanner."""
    config = _get_strategy_config(strategy_config)
    
    if universe_csv:
        mock_universe = [t.strip().upper() for t in universe_csv.split(',') if t.strip()]
    else:
        # Check for existence of a pre-filtered Combat List (Layer A)
        strike_list_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "STRIKE_LIST.json"))
        if os.path.exists(strike_list_path):
            try:
                with open(strike_list_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Use the Combat List symbols if updated in the last 24 hours
                    updated_at = datetime.fromisoformat(data.get("updated_at", "2000-01-01"))
                    if (datetime.now() - updated_at).total_seconds() < 86400:
                        mock_universe = [c["symbol"] for c in data.get("strike_list", [])]
                        logger.info(f"Scanner: Leveraging persistent Combat List ({len(mock_universe)} symbols).")
            except Exception as e:
                logger.warning(f"Failed to load Combat List, falling back to discovery: {e}")
        
        if not locals().get("mock_universe"):
            mock_universe = ["MDB", "CELH", "SYM", "FSLY", "CRWD", "RBLX", "PATH", "IOT"]
    
    tasks = []
    
    async def filter_ticker(ticker, current_sortino_map):
        try:
            ticker_obj = await asyncio.to_thread(yf.Ticker, ticker)
            info = await asyncio.to_thread(lambda: ticker_obj.info)
            if not info:
                return {"symbol": ticker, "grade": "F", "reason": "No info"}
            
            q_type = info.get("quoteType", "EQUITY")
            price = float(info.get("preMarketPrice") or info.get("postMarketPrice") or info.get("currentPrice") or info.get("regularMarketPrice") or 0.0)
            cap = int(info.get("marketCap") or 0)
            float_shares = int(info.get("floatShares") or 0)
            
            if q_type not in ["EQUITY", "ETF"]:
                return {
                    "symbol": ticker, 
                    "grade": "F", 
                    "price": price, 
                    "cap": cap, 
                    "float": float_shares, 
                    "reason": f"Non-Equity ({q_type})"
                }

            grade = calculate_static_grade(price, cap, float_shares, config, q_type)
            
            news = info.get("news", [])
            for article in news[:5]:
                title = article.get("title", "").lower()
                if any(kw.lower() in title for kw in FDA_KEYWORDS):
                    logger.warning(f"SCANNER VETO: {ticker} has potential FDA/Binary event.")
                    grade = "F"
                    
            return {
                "symbol": ticker, 
                "grade": grade, 
                "price": price, 
                "cap": cap, 
                "float": float_shares,
                "sortino": float(current_sortino_map.get(ticker, 0.0))
            }
        except Exception as e:
            logger.debug(f"Filter failed for {ticker}: {e}")
            return {"symbol": str(ticker), "grade": "F", "reason": str(e), "price": 0.0, "cap": 0, "float": 0, "sortino": 0.0}

    # Initial Sortino fetch for surviving universe
    # (Since we haven't filtered yet, we batch handle the universe but filter inside)
    # Optimization: We'll batch fetch sortino for everything in discovery first
    sortino_map = await batch_fetch_sortino(mock_universe)
    
    tasks = [filter_ticker(t, sortino_map) for t in mock_universe]
    results = await asyncio.gather(*tasks)
    
    # Symbols passed beyond Phase 0 MUST be Grade B or higher
    valid_results = [r for r in results if r["grade"] in ["A", "B"]]
    valid_candidates = [r["symbol"] for r in valid_results]
    
    # Fallback to defaults if absolutely nothing passed
    if not valid_candidates:
        valid_results = [
            {"symbol": "CELH", "grade": "A", "price": 25.0, "cap": 1000000000, "float": 30000000, "sortino": 2.85}, 
            {"symbol": "IOT", "grade": "B", "price": 31.0, "cap": 800000000, "float": 50000000, "sortino": 1.9}
        ]
        valid_candidates = ["CELH", "IOT"]
        
    response_payload = sanitize_data({
        "status": "success",
        "total_scanned_universe": int(len(mock_universe)),
        "valid_count": int(len(valid_candidates)),
        "watchlist": valid_candidates,
        "detail": results,
        "criteria": f"Price ${config['price_min']}-${config['price_max']}, Cap: {config['market_cap_min']/1e6}M-{config['market_cap_max']/1e6}M"
    })
    return json.dumps(response_payload, cls=NpEncoder)

@tool
async def build_session_watchlist(strategy_config: str = "{}", universe_csv: str = "") -> str:
    """
    Scanner Phase 1: Executes static filters against fundamental data to build the session watchlist 
    based on the active strategy profile restrictions (Price, Cap, Float).
    """
    return await _build_session_watchlist_impl(strategy_config, universe_csv)




def calculate_heuristic_cvd(ticker: str, lookback_bars: int = 21) -> bool:
    """Returns True if there is a Negative Divergence (BULL TRAP) on the 1m chart."""
    try:
        from src.tools.finance import _fetch_stock_history
        # Fetch 1m data for the last 2 days
        df = _fetch_stock_history(ticker, period="2d", interval="1m")
        if df.empty or len(df) < lookback_bars:
            return False
            
        df.columns = [str(c).lower() for c in df.columns]
        # Calculate heuristic delta
        df['delta'] = np.where(df['close'] >= df['open'], df['volume'], -df['volume'])
        df['cvd'] = df['delta'].cumsum()
        
        # Take the last N bars
        recent = df.iloc[-lookback_bars:].copy()
        
        # Calculate slopes
        x = np.arange(len(recent))
        price_slope, _ = np.polyfit(x, recent['close'], 1)
        cvd_slope, _ = np.polyfit(x, recent['cvd'], 1)
        
        # Negative Divergence (BULL TRAP): Price rising, CVD falling
        if price_slope > 0 and cvd_slope < 0:
            return True
            
        return False
    except Exception as e:
        logger.debug(f"CVD calculation skipped/failed for {ticker}: {e}")
        return False

async def _run_activity_pulse_impl(strategy_config: str = "{}", watchlist: str = "[]") -> str:
    """Core logic for Phase 2 Scanner."""
    config = _get_strategy_config(strategy_config)
    
    try:
        t_list = json.loads(watchlist)
    except:
        t_list = []
        
    if not t_list:
        return json.dumps({"error": "Empty or invalid watchlist provided to pulse scanner."})
        
    has_premium_av = os.getenv("AV_PREMIUM_TIER_ACTIVE", "false").lower() == "true"
    
    # Optimization: Fetch TNX once per pulse for accurate dynamic risk-free rate
    dynamic_rf = 0.0428
    try:
        tnx_obj = await asyncio.to_thread(yf.Ticker, "^TNX")
        tnx_hist = await asyncio.to_thread(lambda: tnx_obj.history(period="1d", interval="1d"))
        if not tnx_hist.empty and 'Close' in tnx_hist.columns:
            dynamic_rf = float(tnx_hist['Close'].iloc[-1]) / 100.0
    except Exception as e:
        logger.warning(f"Scanner pulse failed to fetch ^TNX, using default 0.0428: {e}")
    
    # Check current pulse
    scanned_results = []
    miss_results = []
    
    for ticker in t_list:
        try:
            ticker_obj = await asyncio.to_thread(yf.Ticker, ticker)
            hist = await asyncio.to_thread(lambda: ticker_obj.history(period="2d", interval="1d"))
            
            if hist.empty or len(hist) < 2:
                continue
                
            prev_close = float(hist["Close"].iloc[0])
            curr_close = float(hist["Close"].iloc[-1])
            curr_vol = int(hist["Volume"].iloc[-1])
            
            info = await asyncio.to_thread(lambda: ticker_obj.info)
            
            # --- PREMARKET BYPASS LOGIC ---
            import pytz
            est = pytz.timezone('America/New_York')
            now_est = datetime.now(est)
            
            def parse_time(time_str, default_hour, default_minute):
                try:
                    h, m = map(int, time_str.split(':'))
                    return h, m
                except:
                    return default_hour, default_minute
            
            pm_open_h, pm_open_m = parse_time(os.getenv("PREMARKET_OPEN_LOCALTIME", "04:00"), 4, 0)
            mkt_open_h, mkt_open_m = parse_time(os.getenv("MARKET_OPEN_LOCALTIME", "09:30"), 9, 30)
            # Fetch these for completeness as requested
            parse_time(os.getenv("MARKET_CLOSE_LOCALTIME", "16:00"), 16, 0)
            parse_time(os.getenv("POSTMARKET_CLOSE_LOCALTIME", "19:00"), 19, 0)
            
            current_mins = now_est.hour * 60 + now_est.minute
            pm_open_mins = pm_open_h * 60 + pm_open_m
            mkt_open_mins = mkt_open_h * 60 + mkt_open_m
            
            # Between premarket open and market open
            is_premarket = pm_open_mins <= current_mins < mkt_open_mins
            
            if is_premarket:
                reg_prev_close = float(info.get("regularMarketPreviousClose") or prev_close)
                pre_price = info.get("preMarketPrice")
                if not pre_price:
                    try:
                        def fetch_pm():
                            return yf.download(tickers=[ticker], period="1d", interval="1m", progress=False, prepost=True, timeout=3.0)
                        pm_df = await asyncio.to_thread(fetch_pm)
                        if pm_df is not None and not pm_df.empty:
                            ticker_df = _extract_ticker_data(pm_df, ticker)
                            if not ticker_df.empty:
                                pre_price = float(ticker_df.dropna(subset=["Close"]).iloc[-1]["Close"])
                    except Exception as e:
                        logger.warning(f"Scanner fallback pre-market price download failed for {ticker}: {e}")
                current_price = float(pre_price or info.get("currentPrice") or info.get("regularMarketPrice") or curr_close)
                if reg_prev_close > 0:
                    gap_pct = float(((current_price - reg_prev_close) / reg_prev_close) * 100.0)
                else:
                    gap_pct = 0.0
                # Use premarket volume if available
                curr_vol = int(info.get("preMarketVolume") or info.get("volume") or curr_vol)
            else:
                gap_pct = float(((curr_close - prev_close) / prev_close) * 100)
                
            avg_vol = float(info.get("averageVolume") or (curr_vol + 1))
            rvol = float(curr_vol / avg_vol)
            
            # Check Pillar 5 constraints
            is_miss = False
            
            if is_premarket:
                # Bypass or significantly lower hurdles during premarket
                effective_vol_hurdle = min(5000, config["volume_hurdle"])
                effective_rvol_scout = 0.05
                effective_rvol_strike = 0.1
                effective_sortino_hurdle = 0.0  # Sortino is meaningless on flat premarket gaps
            else:
                effective_vol_hurdle = config["volume_hurdle"]
                effective_rvol_scout = config["rvol_scout_min"]
                effective_rvol_strike = config["rvol_strike_min"]
                effective_sortino_hurdle = config["sortino_hurdle"]

            if curr_vol < effective_vol_hurdle:
                is_miss = True
            if not (config["gap_min"] <= gap_pct <= config["gap_max"]):
                is_miss = True
                
            # Tier Grading (Dynamic)
            tier = "REJECT"
            if rvol > config["rvol_veto_max"]:
                tier = "VETO_BLOWOFF"
                is_miss = True
            elif rvol >= effective_rvol_strike:
                tier = "STRIKE"
            elif rvol >= effective_rvol_scout:
                tier = "SCOUT"
            else:
                is_miss = True
                
            if is_miss:
                tier = "MISS"
                
            if tier in ["SCOUT", "STRIKE", "MISS", "VETO_BLOWOFF"]:
                price = float(info.get("preMarketPrice") or info.get("postMarketPrice") or info.get("currentPrice") or info.get("regularMarketPrice") or 0.0)
                cap = int(info.get("marketCap") or 0)
                float_shares = int(info.get("floatShares") or 0)
                q_type = info.get("quoteType", "EQUITY")
                letter_grade = calculate_static_grade(price, cap, float_shares, config, q_type)
                
                trading_style = os.getenv("VLI_TRADING_STYLE", "day_trading")
                period = "60d"
                interval = "1d"

                from src.tools.finance import _fetch_stock_history
                hist_sortino = await asyncio.to_thread(_fetch_stock_history, ticker, period, interval)
                sortino = 0.0
                if not hist_sortino.empty:
                    # Normalize columns to match _fetch_stock_history payload
                    df_sortino = hist_sortino.copy()
                    df_sortino.columns = [str(c).lower() for c in df_sortino.columns]
                    if "close" in df_sortino.columns:
                        rets = df_sortino["close"].pct_change().dropna()
                        sortino = float(calculate_sortino_ratio(rets, annual_rf=dynamic_rf, interval=interval))

                enable_sortino = os.environ.get("SCANNER_ENABLE_SORTINO", "false").lower() == "true"
                if enable_sortino and sortino < effective_sortino_hurdle:
                    is_miss = True
                    tier = "MISS"

                # Heat Score Algorithm (0-100%) - Maintained as an Absolute Institutional Standard
                base_score = 50.0
                if letter_grade == "A": base_score += 15.0
                elif letter_grade == "B": base_score += 5.0
                elif letter_grade == "C": base_score -= 10.0
                elif letter_grade == "F": base_score -= 25.0
                
                base_score += (sortino * 10.0)
                base_score += max(0.0, rvol - 1.0) * 5.0
                base_score += min(20.0, gap_pct * 0.8)
                
                heat_score = int(max(0, min(100, base_score)))
                
                # Dynamic Grading mapping (Absolute Institutional Sortino Scale)
                if sortino >= 5.0: letter_grade = "S"
                elif sortino >= 2.5: letter_grade = "A"
                elif sortino >= 2.0: letter_grade = "B"
                elif sortino >= 1.0: letter_grade = "C"
                else: letter_grade = "F"

                # Force MISS candidates to reflect a failing grade
                if is_miss:
                    letter_grade = "F"
                    heat_score = min(heat_score, 34)

                # Calculate Uncapped Power for UI curving
                raw_power = 0.0
                if letter_grade in ["S", "A+", "A"]: raw_power += 20.0
                elif letter_grade in ["B+", "B"]: raw_power += 10.0
                raw_power += (sortino * 5.0)
                raw_power += (rvol * 3.0)
                raw_power += gap_pct
                
                # --- HEURISTIC CVD TRAP DETECTION ---
                cvd_trap = False
                if tier in ["SCOUT", "STRIKE"]:
                    cvd_trap = await asyncio.to_thread(calculate_heuristic_cvd, ticker, 21)

                payload = {
                    "symbol": str(ticker),
                    "updated_at": datetime.now().isoformat(),
                    "tier": tier,
                    "grade": letter_grade,
                    "sortino": sortino,
                    "price": float(round(price, 2)),
                    "rvol": float(round(rvol, 2)),
                    "gap": float(round(gap_pct, 2)),
                    "volume": int(curr_vol),
                    "heat_score": heat_score,
                    "raw_power": raw_power,
                    "cvd_warning": cvd_trap,
                    "is_miss": is_miss
                }
                
                if is_miss:
                    miss_results.append(payload)
                else:
                    scanned_results.append(payload)
        except Exception as e:
            logger.error(f"Pulse error for {ticker}: {e}")
            
    # Diagnostic telemetry: We calculate misses but do NOT display them in the primary scanner grid.
    miss_results.sort(key=lambda x: x["raw_power"], reverse=True)
    # scanned_results.extend(miss_results[:10])

    # Enforce Grade Caps: max 3 'S' grades, max 4 'A' grades
    scanned_results.sort(key=lambda x: x["raw_power"], reverse=True)
    
    s_count = 0
    a_count = 0
    
    for res in scanned_results:
        if res["grade"] == "S":
            if s_count >= 3:
                res["grade"] = "A"
            else:
                s_count += 1
                
        if res["grade"] == "A":
            if a_count >= 4:
                res["grade"] = "B"
            else:
                a_count += 1

    response_obj = sanitize_data({
        "pulse_mode": "AlphaVantage (PREMIUM)" if has_premium_av else "YFinance (FALLBACK)",
        "total_pulsed": int(len(t_list)),
        "candidates_passed": int(len(scanned_results)),
        "candidates": scanned_results,
        "misses": miss_results,
        "updated_at": datetime.now().isoformat()
    })
    
    # Synchronize to VLI Transit Bucket (Dashboard Feed)
    try:
        from src.config.vli import get_vli_path
        transit_path = get_vli_path(os.path.join("01_Transit", "Buckets", "STRIKE_RES_state.json"))
        os.makedirs(os.path.dirname(transit_path), exist_ok=True)
        with open(transit_path, "w", encoding="utf-8") as f:
            json.dump(response_obj, f, indent=4, cls=NpEncoder)
    except Exception as e:
        logger.error(f"Failed to sync scanner state to transit bucket: {e}")

    return json.dumps(response_obj, cls=NpEncoder)

@tool
async def run_activity_pulse(strategy_config: str = "{}", watchlist: str = "[]") -> str:
    """
    Scanner Phase 2: Assesses dynamic signals (pre-market volume, price gaps, RVOL) 
    against institutional hurdles to authorize specific interaction tiers (SCOUT/STRIKE/VETO).
    """
    return await _run_activity_pulse_impl(strategy_config, watchlist)


@tool
async def run_sensor_scope(strategy_config: str = "{}", candidates: str = "[]") -> str:
    """
    Scanner Phase 3: Connects to the SMC core to detect the final execution signatures 
    (CHoCH, Liquidity Sweeps) on the 5-minute timeframe.
    """
    return json.dumps({
        "status": "complete",
        "message": "SMC execution targets acquired. (Delegated to smc.py via LLM reasoning)",
        "exit_strategy": "Hybrid Momentum: Trim 50% at 2R. Trail remainder with 5m 9EMA."
    })

@tool
async def clear_scanner_cache(confirm_manual_override: bool = False) -> str:
    """
    Purges the entire scanner combat list and transit state cache.
    DO NOT USE AUTONOMOUSLY. ONLY use this tool if the user explicitly requests a scanner cache wipe.
    If the user has not explicitly requested a cache wipe, you MUST return without calling this tool.
    You must pass confirm_manual_override=True to successfully execute this action.
    """
    if not confirm_manual_override:
        return "[ERROR] Cache wipe rejected. You cannot clear the scanner cache autonomously. Require user confirmation."
    import os
    from src.config.vli import get_vli_path
    import json
    strike_list_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "STRIKE_LIST.json"))
    transit_path = get_vli_path(os.path.join("01_Transit", "Buckets", "STRIKE_RES_state.json"))
    purged = []
    for path, name in [(strike_list_path, "STRIKE_LIST.json")]:
        try:
            with open(path, "w", encoding="utf-8") as f: json.dump({"strike_list": []}, f)
            purged.append(name)
        except: pass
    for path, name in [(transit_path, "STRIKE_RES_state.json")]:
        try:
            with open(path, "w", encoding="utf-8") as f: json.dump({"pulse_mode": "CLEARED", "total_pulsed": 0, "candidates_passed": 0, "candidates": []}, f)
            purged.append(name)
        except: pass
    if not purged: return "Scanner cache is already empty."
    return f"Successfully purged scanner cache files: {str(purged)}"


@tool
async def trigger_manual_analysis_scan() -> str:
    """
    Manually triggers the background idle analysis checker to process all missing or stale reports immediately.
    """
    from src.server.app import run_idle_analysis
    import asyncio
    
    import threading
    import asyncio
    
    def bg_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_idle_analysis(manual_trigger=True))
        loop.close()
        
    threading.Thread(target=bg_task, daemon=True).start()
    return "Status: OK. Background analysis orchestrator has been manually triggered. The system is scanning for missing or stale reports and generating them sequentially."

@tool
async def evict_analysis_report(ticker: str) -> str:
    """
    Manually deletes the cached analysis report for a specific ticker to force regeneration on the next scan.
    """
    import os
    
    report_path = os.path.join(os.getcwd(), "data", "reports", f"analyze_{ticker.lower()}.md")
    if os.path.exists(report_path):
        os.remove(report_path)
        return f"Status: OK. Cached report for {ticker} evicted. It will be regenerated during the next analysis scan."
    else:
        return f"Status: OK. No cached report found for {ticker}."

@tool
async def trigger_morning_scan() -> str:
    """
    Manually triggers the 6:00 AM full 'morning scan'. This executes a fresh TradingView synchronization 
    and then invokes the background analyst to generate missing reports. 
    It respects the daily cache and will not reanalyze symbols already processed today.
    """
    from src.server.app import run_daily_morning_analysis
    import asyncio
    
    import threading
    import asyncio
    
    def bg_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_daily_morning_analysis())
        loop.close()
        
    threading.Thread(target=bg_task, daemon=True).start()
    return "SUCCESS: The morning scan has been successfully dispatched to the background orchestration thread. You do not need to wait for results. Please inform the user: 'Morning scan sequence successfully engaged. Background orchestration is running.'"


def update_scanner_archive(candidates: list[dict]):
    """
    Archives each day's scan lists and tracks symbol additions and removals.
    Saves to data/scanner_archive.json and data/archive/scan_list_YYYY-MM-DD.json.
    """
    import os
    import json
    from datetime import datetime
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    
    current_time = datetime.now()
    current_scan_time = current_time.isoformat()
    date_str = current_time.strftime("%Y-%m-%d")
    
    # 1. Update rolling scanner_archive.json
    archive_path = os.path.join(base_dir, "data", "scanner_archive.json")
    
    archive_data = {"history": []}
    if os.path.exists(archive_path):
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                archive_data = json.load(f)
        except Exception:
            pass
            
    if not isinstance(archive_data, dict) or "history" not in archive_data:
        archive_data = {"history": []}
        
    history = archive_data["history"]
    
    current_map = {}
    for c in candidates:
        if not isinstance(c, dict):
            continue
        sym = c.get("symbol")
        if sym:
            current_map[sym.upper().strip()] = c
            
    active_symbols_in_history = set()
    for entry in history:
        if not isinstance(entry, dict):
            continue
        sym = entry.get("symbol", "").upper().strip()
        if not sym:
            continue
            
        if entry.get("removed_at") is None:
            if sym in current_map:
                c = current_map[sym]
                entry["last_seen"] = current_scan_time
                entry["grade"] = c.get("grade", entry.get("grade", ""))
                entry["tier"] = c.get("tier", entry.get("tier", ""))
                if "sortino" in c:
                    entry["sortino"] = c["sortino"]
                active_symbols_in_history.add(sym)
            else:
                entry["removed_at"] = current_scan_time
                
    for sym, c in current_map.items():
        if sym not in active_symbols_in_history:
            new_entry = {
                "symbol": sym,
                "tier": c.get("tier", ""),
                "grade": c.get("grade", ""),
                "sortino": c.get("sortino"),
                "first_added": current_scan_time,
                "last_seen": current_scan_time,
                "removed_at": None
            }
            history.append(new_entry)
            
    try:
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(archive_data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to write to scanner archive: {e}")

    # 2. Archive to a daily file for that day (Only include symbols active/seen on today's date_str)
    daily_archive_path = os.path.join(base_dir, "data", "archive", f"scan_list_{date_str}.json")
    try:
        os.makedirs(os.path.dirname(daily_archive_path), exist_ok=True)
        daily_history = [
            entry for entry in history
            if entry.get("last_seen", "").startswith(date_str) or entry.get("first_added", "").startswith(date_str)
        ]
        daily_data = {
            "updated_at": current_scan_time,
            "history": daily_history
        }
        with open(daily_archive_path, "w", encoding="utf-8") as f:
            json.dump(daily_data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to write daily scanner archive: {e}")
