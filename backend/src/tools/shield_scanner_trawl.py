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
from src.tools.scanner import _get_strategy_config, batch_fetch_sortino

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
COMBAT_LIST_PATH = Path(__file__).parent.parent.parent / "data" / "SHIELD_COMBAT_LIST.json"
# TV Shield Scan Minimums: Market Cap >= 300M, Price >= 15, Volume >= 1M, Float >= 100M
# We use cap_smallover (>= 300M) and ta_sma200_pa (Price > SMA200) to keep initial results broad but aligned with TV.
# sh_price_o15, sh_vol_o1000, sh_float_o100 are handled natively but can also be enforced here to reduce load.
FINVIZ_FILTERS = "f=cap_smallover,ta_sma200_pa,sh_price_o15,sh_vol_o1000,sh_float_o100&o=-change"

def _get_shield_config(strategy_config: str) -> Dict[str, Any]:
    """Provides configuration for the APEX SHIELD SCAN."""
    default_config = {
        "price_min": 15.0,
        "price_max": 999999.0,
        "market_cap_min": 300_000_000,
        "market_cap_max": 999999999999.0, # No real max limit
        "float_min": 100_000_000,
        "float_max": 999999999999.0, # No real max limit
        "volume_hurdle": 1_000_000,
        "gap_min": -20.0,
        "gap_max": 500.0,
        "rvol_scout_min": 1.0,
        "rvol_strike_min": 2.0,
        "rvol_veto_max": 100.0,
        "sortino_hurdle": 2.0,
        "rs_hurdle": 90,
        "binary_veto_hours": 24
    }
    if not strategy_config:
        return default_config
    try:
        if isinstance(strategy_config, str):
            custom = json.loads(strategy_config)
            default_config.update(custom)
        elif isinstance(strategy_config, dict):
            default_config.update(strategy_config)
    except Exception as e:
        logger.error(f"Failed to parse scanner strategy config: {e}. Using defaults.")
        
    if os.getenv("VLI_TRADING_STYLE", "day_trading") == "day_trading":
        default_config["sortino_hurdle"] *= 10.0
        
    return default_config

@tool
async def run_shield_trawl(strategy_config: str = "{}") -> Dict[str, Any]:
    """
    LAYER A: THE SHIELD TRAWL
    Filters the market for mid-to-mega cap "Shields" with elite defensive profiles.
    """
    config = _get_shield_config(strategy_config)
    os.makedirs(os.path.dirname(COMBAT_LIST_PATH), exist_ok=True)

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
                url_base = f"https://elite.finviz.com/screener.ashx?v=111&{FINVIZ_FILTERS}"
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
                if c_sortino < 0.0: # Long-range Sortino Floor (No bleeding assets)
                    logger.info(f"Rejected {ticker} - Failed Long-Range Sortino Floor ({c_sortino})")
                    return None
                
                # Calculate Sortino-based fallback grading dynamically based on the day trading hurdle
                effective_hurdle = config.get("sortino_hurdle", 2.0)
                grade = "S" if c_sortino >= effective_hurdle * 1.5 else ("A" if c_sortino >= effective_hurdle * 1.2 else "B")
                
                return {
                    **c,
                    "price": round(price, 2),
                    "volume": volume,
                    "beta": round(beta, 2),
                    "dividend_yield": round(div_yield * 100, 2),
                    "float": f_shares,
                    "market_cap": m_cap,
                    "sortino": c_sortino,
                    "grade": grade,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.debug(f"Verification failed for {ticker}: {e}")
                return None

    logger.info(f"Running Fundamental Verification (SHIELD Defense)...")
    verification_tasks = [verify_candidate(c) for c in candidates]
    verified_candidates = await asyncio.gather(*verification_tasks)
    verified_list = [v for v in verified_candidates if v is not None]

    # Dynamically rank by highest Sortino ratio
    verified_list.sort(key=lambda x: -x.get("sortino", 0.0))
    
    # Strictly limit to top 10
    verified_list = verified_list[:10]

    if verified_list:
        max_sortino = verified_list[0].get("sortino", 0.0)
        for v in verified_list:
            s = v.get("sortino", 0.0)
            if s >= max_sortino * 0.8:
                v["grade"] = "S"
            elif s >= max_sortino * 0.5:
                v["grade"] = "A"
            else:
                v["grade"] = "B"

    # 4. Persistence
    combat_list = {
        "updated_at": datetime.now().isoformat(),
        "macro": {
            "shield_mode": "ACTIVE"
        },
        "universe_size": total_count or len(candidates),
        "verified_count": len(verified_list),
        "combat_list": verified_list
    }

    clean_combat_list = sanitize_data(combat_list)

    with open(COMBAT_LIST_PATH, "w", encoding="utf-8") as f:
        json.dump(clean_combat_list, f, indent=4)

    logger.info(f"SHIELD Combat List synchronized. {len(verified_list)} verified shields in the bunker.")
    return clean_combat_list

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    # For testing execution
    args = sys.argv[1:]
    if "--run" in args:
        asyncio.run(run_shield_trawl.ainvoke({}))
