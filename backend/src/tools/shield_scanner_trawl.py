import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from playwright.async_api import async_playwright
import yfinance as yf
import pandas as pd
import numpy as np

from langchain_core.tools import tool
from src.tools.scanner import load_strategy_constraints, _get_strategy_config, batch_fetch_sortino

logger = logging.getLogger(__name__)

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

# Constants
STRIKE_LIST_PATH = Path(__file__).parent.parent.parent / "data" / "STRIKE_LIST.json"
# TV Shield Scan Minimums: Market Cap >= 300M, Price >= 15, Volume >= 1M, Float >= 100M (No maximum market cap limit)
# We use cap_smallover (>= 300M) and ta_sma200_pa (Price > SMA200) to keep initial results broad but aligned with TV.
# sh_price_o15, sh_vol_o1000, sh_float_o100 are handled natively but can also be enforced here to reduce load.
FINVIZ_FILTERS = "f=cap_smallover,ta_sma200_pa,sh_price_o15,sh_vol_o1000,sh_float_o100&o=-change"

def _get_shield_config(strategy_config: str) -> Dict[str, Any]:
    """Provides configuration for the APEX SHIELD SCAN."""
    strategy_name = "shield"
    custom_overrides = {}
    
    if strategy_config:
        try:
            if isinstance(strategy_config, str):
                custom_overrides = json.loads(strategy_config)
            elif isinstance(strategy_config, dict):
                custom_overrides = strategy_config
            
            if isinstance(custom_overrides, dict):
                strategy_name = custom_overrides.get("strategy_name", "shield")
        except Exception as e:
            logger.error(f"Failed to parse scanner strategy config: {e}. Using defaults.")
            
    config = load_strategy_constraints(strategy_name)
    if isinstance(custom_overrides, dict):
        config.update(custom_overrides)
        
    return config

@tool
async def run_shield_trawl(strategy_config: str = "{}") -> Dict[str, Any]:
    """
    LAYER A: THE SHIELD TRAWL
    Filters the market for mid-to-mega cap "Shields" with elite defensive profiles.
    """
    config = _get_shield_config(strategy_config)
    os.makedirs(os.path.dirname(STRIKE_LIST_PATH), exist_ok=True)

    # Dynamically build Finviz filters matching Shield strategy constraints
    price_min = config.get("price_min", 15.0)
    float_min = config.get("float_min", 100_000_000)
    volume_hurdle = config.get("volume_hurdle", 1_000_000)
    
    price_filter = ""
    if price_min >= 15.0:
        price_filter = "sh_price_o15"
    elif price_min >= 10.0:
        price_filter = "sh_price_o10"
        
    float_filter = ""
    if float_min >= 100_000_000:
        float_filter = "sh_float_o100"
    elif float_min >= 50_000_000:
        float_filter = "sh_float_o50"
        
    vol_filter = ""
    if volume_hurdle >= 1_000_000:
        vol_filter = "sh_vol_o1000"
    elif volume_hurdle >= 500_000:
        vol_filter = "sh_vol_o500"
        
    filter_parts = ["cap_smallover", "ta_sma200_pa"]
    if price_filter:
        filter_parts.append(price_filter)
    if float_filter:
        filter_parts.append(float_filter)
    if vol_filter:
        filter_parts.append(vol_filter)
        
    finviz_filters = "f=" + ",".join(filter_parts) + "&o=-change"
    logger.info(f"Dynamic Shield Finviz Filters generated: {finviz_filters}")

    candidates = []
    total_count = 0
    total_pages = 0

    # 2. Stage 1: Acquisition (Staged CSV or Elite Export or Pagination Fallback)
    csv_path = Path(__file__).parent.parent.parent / "data" / "finviz_shield_export.csv"
    seen_symbols = set()
    use_acquisition = True
    
    if csv_path.exists():
        try:
            logger.info(f"Found staged Elite Export CSV at {csv_path}. Processing locally...")
            df = pd.read_csv(csv_path)
            if "Ticker" in df.columns:
                ticker_list = df["Ticker"].tolist()
                for symbol in ticker_list:
                    s = str(symbol).strip().upper()
                    if s and s.isalpha() and s not in seen_symbols and 1 <= len(s) <= 5:
                        seen_symbols.add(s)
                        candidates.append({
                            "symbol": s,
                            "price": 0.0,
                            "change": "0%",
                            "volume": "0",
                            "source": "finviz_shield"
                        })
                logger.info(f"Staged Export successful. Extracted {len(candidates)} symbols.")
                use_acquisition = False
            else:
                logger.warning("Staged CSV missing 'Ticker' column. Proceeding to automated acquisition.")
        except Exception as e:
            logger.error(f"Failed to read staged CSV: {e}. Proceeding to automated acquisition.")

    if use_acquisition:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # We try to use a standard user agent to avoid bot detection
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            # Inject Elite Cookies for Authentication
            cookies = [
                {"name": "finviz_t", "value": "0547e391-6282-4ac8-846a-4ee32491d8e6", "domain": ".finviz.com", "path": "/"},
                {"name": "chartsTheme", "value": "dark", "domain": ".finviz.com", "path": "/"},
                {"name": "notice-newsletter", "value": "show", "domain": ".finviz.com", "path": "/"}
            ]
            await context.add_cookies(cookies)
            
            page = await context.new_page()

            try:
                # Use elite subdomain for subscribers to ensure export button is visible
                url_base = f"https://elite.finviz.com/screener.ashx?v=111&{finviz_filters}"
                logger.info(f"Initiating SHIELD Elite Trawl: {url_base}")
                
                # Navigate with a generous timeout for the heavy Elite site
                await page.goto(url_base, wait_until="domcontentloaded", timeout=45000)
                
                # Get total count for metadata and fallback logic
                try:
                    await page.wait_for_selector(".count-text", timeout=15000)
                    count_text = await page.inner_text(".count-text")
                    total_count = int(count_text.split("/")[-1].split("Total")[0].strip())
                    total_pages = min((total_count // 20) + (1 if total_count % 20 > 0 else 0), 2)
                    logger.info(f"Total candidates matching SHIELD filters: {total_count} (Capped at {total_pages} pages).")
                except:
                    logger.warning("Could not detect total count from .count-text. Using fallback: 3 pages.")
                    total_pages = 3

                use_pagination = True
                
                # --- ELITE EXPORT ATTEMPT ---
                try:
                    logger.info("Attempting Elite Export (CSV)...")
                    async with page.expect_download(timeout=30000) as download_info:
                        export_link = await page.query_selector("a.tab-link[href*='export.ashx']")
                        if export_link:
                            await export_link.click()
                        else:
                            raise Exception("Export link not found on page.")
                    
                    download = await download_info.value
                    await download.save_as(str(csv_path))
                    
                    df = pd.read_csv(csv_path)
                    if "Ticker" in df.columns:
                        ticker_list = df["Ticker"].tolist()
                        for symbol in ticker_list:
                            s = str(symbol).strip().upper()
                            if s and s.isalpha() and s not in seen_symbols and 1 <= len(s) <= 5:
                                seen_symbols.add(s)
                                candidates.append({
                                    "symbol": s,
                                    "price": 0.0,
                                    "change": "0%",
                                    "volume": "0",
                                    "source": "finviz_shield"
                                })
                        logger.info(f"Elite Export successful. Processed {len(candidates)} symbols from CSV.")
                        use_pagination = False
                except Exception as e:
                    logger.warning(f"Elite Export failed: {e}. Falling back to manual pagination.")

                # --- PAGINATION FALLBACK ---
                if use_pagination:
                    logger.info("Initiating multi-page trawl fallback...")
                    for p_idx in range(total_pages):
                        start_r = (p_idx * 20) + 1
                        page_url = f"{url_base}&r={start_r}"
                        logger.info(f"Scanned page [{p_idx+1}/{total_pages}]: {page_url}")
                        
                        if p_idx > 0: # First page already loaded
                            await page.goto(page_url, wait_until="domcontentloaded", timeout=25000)
                        
                        links = await page.query_selector_all("a.screener-link-primary")
                        if not links:
                            links = await page.query_selector_all("a[href*='t=']")

                        for link in links:
                            symbol = (await link.inner_text()).strip().upper()
                            if symbol and symbol.isalpha() and symbol not in seen_symbols and 1 <= len(symbol) <= 5:
                                seen_symbols.add(symbol)
                                candidates.append({
                                    "symbol": symbol,
                                    "price": 0.0,
                                    "change": "0%",
                                    "volume": "0",
                                    "source": "finviz_shield"
                                })
                        
                        if p_idx < total_pages - 1:
                            await asyncio.sleep(1.5) # Anti-bot delay
                    
                    logger.info(f"Pagination complete. Found {len(candidates)} symbols.")

            except Exception as e:
                logger.error(f"Finviz SHIELD Trawl failed: {e}")
            finally:
                await browser.close()

    if csv_path.exists():
        try:
            os.rename(csv_path, str(csv_path) + f".processed_{int(time.time())}")
            logger.info(f"Cleaned up {csv_path} to prevent stale data reuse.")
        except Exception as e:
            logger.warning(f"Could not clean up {csv_path}: {e}")

    # [UPDATED] Always inject institutional Core baseline to guarantee coverage of all major sectors
    logger.info("[SHIELD] Injecting institutional Core baseline.")
    baseline = [
        # Major Sector ETFs (Macro Coverage)
        "XLE", "XLK", "XLF", "XLV", "XLY", "XLI", "XLP", "XLU", "XLB", "XLRE", "XLC",
        # Energy Rotation Favorites
        "OXY", "APA", "XOM", "CVX", "HAL", "SLB", "VLO", "MPC", "COP",
        # Defense / Aerospace
        "ITA", "RTX", "LMT", "NOC", "GD",
        # Core Utilities
        "NEE", "DUK", "SO", "SRE"
    ]
    for s in baseline:
        if s not in seen_symbols:
            seen_symbols.add(s)
            candidates.append({
                "symbol": s,
                "price": 0.0,
                "change": "0%",
                "volume": "0",
                "source": "fallback_baseline"
            })

    # 3. Stage 2: Precision Verification (Fundamentals)
    symbols = [c["symbol"] for c in candidates]
    logger.info(f"Initiating Stage 2 verification for {len(symbols)} SHIELD candidates...")
    
    sortino_map = await batch_fetch_sortino(symbols)
    
    verified_list = []
    sem = asyncio.Semaphore(5) # Throttle fundamental lookups
    
    async def verify_candidate(c):
        async with sem:
            ticker = c["symbol"]
            
            try:
                ticker_obj = yf.Ticker(ticker)
                
                info = await asyncio.to_thread(lambda: ticker_obj.info)
                price = info.get("preMarketPrice") or info.get("postMarketPrice") or info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
                
                try:
                    fast = ticker_obj.fast_info
                    volume = fast.last_volume or info.get("volume") or 0
                    m_cap = fast.market_cap or info.get("marketCap") or 0
                    if not price:
                        price = fast.last_price or fast.previous_close or 0.0
                except:
                    volume = info.get("volume") or 0
                    m_cap = info.get("marketCap") or 0
                beta = info.get("beta") or 1.0
                div_yield = info.get("dividendYield") or 0.0
                f_shares = info.get("floatShares") or 0
                
                # Pull 1y Sortino
                c_sortino = sortino_map.get(ticker, 0.0)

                # Check Pillar 1 Constraints for Shields
                # Defensive constraints removed to allow for high-quality mid-cap momentum assets
                enable_sortino = os.environ.get("SCANNER_ENABLE_SORTINO", "false").lower() == "true"
                if enable_sortino and c_sortino < 0.0: # Long-range Sortino Floor (No bleeding assets)
                    logger.info(f"Rejected {ticker} - Failed Long-Range Sortino Floor ({c_sortino})")
                    return None
                # Grade will be calculated via relative curve

                
                return {
                    **c,
                    "price": round(price, 2),
                    "volume": volume,
                    "beta": round(beta, 2),
                    "dividend_yield": round(div_yield * 100, 2),
                    "float": f_shares,
                    "market_cap": m_cap,
                    "sortino": c_sortino,
                    "tier": "SHIELD",
                    "grade": "F", # Placeholder, updated via curve
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.debug(f"Verification failed for {ticker}: {e}")
                return None

    logger.info(f"Running Fundamental Verification (SHIELD Defense)...")
    verification_tasks = [verify_candidate(c) for c in candidates]
    verified_candidates = await asyncio.gather(*verification_tasks)
    verified_list = [v for v in verified_candidates if v is not None]

    # Dynamically rank by highest Sortino ratio FIRST
    verified_list.sort(key=lambda x: -x.get("sortino", 0.0))

    # [HARDENING] Rank-Based Uniform Percentile Curve Grading
    # Replaces min/max scaling with pure rank percentiles to enforce a true bell curve of grades
    if verified_list:
        n = len(verified_list)
        for i, v in enumerate(verified_list):
            if n > 1:
                percentile = (n - 1 - i) / (n - 1)
            else:
                percentile = 1.0
            
            heat_score = int(40 + (percentile * 60))
            if heat_score >= 95: grade = "S"
            elif heat_score >= 90: grade = "A+"
            elif heat_score >= 82: grade = "A"
            elif heat_score >= 75: grade = "B+"
            elif heat_score >= 65: grade = "B"
            elif heat_score >= 58: grade = "C+"
            elif heat_score >= 50: grade = "C"
            elif heat_score >= 35: grade = "D"
            else: grade = "F"
            
            v["grade"] = grade
            v["heat_score"] = heat_score

        # Enforce grade caps (max 3 S grades, max 4 A/A+ grades)
        s_count = 0
        a_count = 0
        for v in verified_list:
            if v["grade"] == "S":
                if s_count >= 3:
                    v["grade"] = "A+"
                else:
                    s_count += 1
            
            if v["grade"] in ["A+", "A"]:
                if a_count >= 4:
                    v["grade"] = "B+"
                else:
                    a_count += 1
    
    # 4. Persistence
    existing_list = []
    if STRIKE_LIST_PATH.exists():
        try:
            with open(STRIKE_LIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_list = data if isinstance(data, list) else data.get("strike_list", [])
        except Exception as e:
            logger.warning(f"Could not read existing STRIKE_LIST: {e}")

    # Preserve other tiers
    preserved_list = [c for c in existing_list if c.get("tier") != "SHIELD"]
    combined_list = preserved_list + verified_list

    strike_list = {
        "updated_at": datetime.now().isoformat(),
        "macro": {
            "shield_mode": "ACTIVE"
        },
        "universe_size": total_count or len(candidates),
        "verified_count": len(combined_list),
        "strike_list": combined_list
    }

    clean_strike_list = sanitize_data(strike_list)

    tmp_path = f"{STRIKE_LIST_PATH}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(clean_strike_list, f, indent=4)
    os.replace(tmp_path, STRIKE_LIST_PATH)

    # [ARCHIVE SCAN LISTS]
    try:
        from src.tools.scanner import update_scanner_archive
        update_scanner_archive(clean_strike_list.get("strike_list", []))
    except Exception as e:
        logger.error(f"Failed to archive scan lists: {e}")

    # [WATCHLIST EXPORT - Disabled, only run on user command]
    # try:
    #     logger.info("Exporting TradingView Watchlists...")
    #     import sys
    #     proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    #     if proj_root not in sys.path:
    #         sys.path.append(proj_root)
    #     from scripts.utils.export_tradingview_watchlists import main as run_export
    #     run_export()
    # except Exception as e:
    #     logger.error(f"TradingView Watchlists Export Failed: {e}")

    logger.info(f"SHIELD Combat List synchronized. {len(verified_list)} verified shields in the bunker.")
    return clean_strike_list

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    # For testing execution
    args = sys.argv[1:]
    if "--run" in args:
        asyncio.run(run_shield_trawl.ainvoke({}))
