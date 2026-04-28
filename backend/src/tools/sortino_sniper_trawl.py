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

from src.tools.scanner import batch_fetch_sortino, _get_strategy_config
from src.tools.finance import _normalize_ticker

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
COMBAT_LIST_PATH = Path(__file__).parent.parent.parent / "data" / "SCANNER_COMBAT_LIST.json"
FINVIZ_FILTERS = "f=cap_smallover,sh_float_u100,sh_price_5to50,ta_perf_13w20o"

async def run_background_trawl(strategy_config: str = "{}") -> Dict[str, Any]:
    """
    LAYER A: THE BACKGROUND TRAWL
    Filters the market for mid-cap "Swords" with elite risk-adjusted profiles.
    """
    config = _get_strategy_config(strategy_config)
    os.makedirs(os.path.dirname(COMBAT_LIST_PATH), exist_ok=True)

    # 1. Determine dynamic Sortino Hurdle based on .TNX
    tnx_rate = 4.30 # Conservative default
    try:
        tnx_ticker = yf.Ticker("^TNX")
        tnx_hist = await asyncio.to_thread(lambda: tnx_ticker.history(period="1d"))
        if not tnx_hist.empty:
            tnx_rate = tnx_hist["Close"].iloc[-1]
            logger.info(f"Macro: .TNX rate fetched at {tnx_rate:.2f}")
    except Exception as e:
        logger.warning(f"Failed to fetch .TNX for macro hurdle: {e}. Using default 4.30")

    # Macro Monitor logic: .TNX > 4.30% -> S >= 2.5
    base_hurdle = config.get("sortino_hurdle", 2.0)
    effective_hurdle = 2.5 if tnx_rate > 4.30 else base_hurdle
    
    if os.getenv("VLI_TRADING_STYLE", "day_trading") == "day_trading":
        effective_hurdle *= 10.0
        
    logger.info(f"Bunker Trawl: Effective Sortino Hurdle: {effective_hurdle}")

    candidates = []
    total_count = 0
    total_pages = 0

    # 2. Stage 1: Acquisition (Staged CSV or Elite Export or Pagination Fallback)
    csv_path = Path(__file__).parent.parent.parent / "data" / "finviz_export.csv"
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
                    if s and s.isalnum() and s not in seen_symbols and 1 <= len(s) <= 5:
                        seen_symbols.add(s)
                        candidates.append({
                            "symbol": s,
                            "price": 0.0,
                            "change": "0%",
                            "volume": "0",
                            "source": "finviz_bunker"
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
            # [NEW] Inject Elite Cookies for Authentication
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
                logger.info(f"Initiating Elite Trawl: {url_base}")
                
                # Navigate with a generous timeout for the heavy Elite site
                await page.goto(url_base, wait_until="load", timeout=45000)
                
                # Get total count for metadata and fallback logic
                try:
                    await page.wait_for_selector(".count-text", timeout=15000)
                    count_text = await page.inner_text(".count-text")
                    total_count = int(count_text.split("/")[-1].split("Total")[0].strip())
                    total_pages = (total_count // 20) + (1 if total_count % 20 > 0 else 0)
                    logger.info(f"Total candidates matching filters: {total_count} ({total_pages} pages).")
                except:
                    logger.warning("Could not detect total count from .count-text. Using fallback: 7 pages.")
                    total_pages = 7

                use_pagination = True
                
                # --- ELITE EXPORT ATTEMPT ---
                try:
                    logger.info("Attempting Elite Export (CSV)...")
                    # Wait for download event and click the link at the bottom right
                    async with page.expect_download(timeout=30000) as download_info:
                        # Look for the export link specifically
                        export_link = await page.query_selector("a.tab-link[href*='export.ashx']")
                        if export_link:
                            await export_link.click()
                        else:
                            raise Exception("Export link not found on page.")
                    
                    download = await download_info.value
                    await download.save_as(str(csv_path))
                    
                    # Parse CSV with pandas
                    df = pd.read_csv(csv_path)
                    if "Ticker" in df.columns:
                        ticker_list = df["Ticker"].tolist()
                        for symbol in ticker_list:
                            s = str(symbol).strip().upper()
                            # Strict alphanumeric 1-5 char filter
                            if s and s.isalnum() and s not in seen_symbols and 1 <= len(s) <= 5:
                                seen_symbols.add(s)
                                candidates.append({
                                    "symbol": s,
                                    "price": 0.0,
                                    "change": "0%",
                                    "volume": "0",
                                    "source": "finviz_bunker"
                                })
                        logger.info(f"Elite Export successful. Processed {len(candidates)} symbols from CSV.")
                        use_pagination = False
                    else:
                        logger.warning("CSV downloaded but 'Ticker' column missing. Falling back to pagination.")
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
                            await page.goto(page_url, wait_until="commit", timeout=25000)
                        
                        # Extract from table <a> tags
                        links = await page.query_selector_all("a.screener-link-primary")
                        if not links:
                            links = await page.query_selector_all("a[href*='t=']")

                        for link in links:
                            symbol = (await link.inner_text()).strip().upper()
                            if symbol and symbol.isalnum() and symbol not in seen_symbols and 1 <= len(symbol) <= 5:
                                seen_symbols.add(symbol)
                                candidates.append({
                                    "symbol": symbol,
                                    "price": 0.0,
                                    "change": "0%",
                                    "volume": "0",
                                    "source": "finviz_bunker"
                                })
                        
                        if p_idx < total_pages - 1:
                            await asyncio.sleep(1.5) # Anti-bot delay
                    
                    logger.info(f"Pagination complete. Found {len(candidates)} symbols.")

            except Exception as e:
                logger.error(f"Finviz Bunker Trawl failed: {e}")
            finally:
                await browser.close()

    if not candidates:
        return {"status": "error", "message": "No candidates identified during Stage 1."}

    # 3. Stage 2: Precision Verification (Chunked Sortino & Fundamentals)
    symbols = [c["symbol"] for c in candidates]
    logger.info(f"Initiating Stage 2 verification for {len(symbols)} candidates...")
    
    # [NEW] Chunked Sortino Calculation (Anti-Rate-Limit)
    CHUNK_SIZE = 30
    sortino_map = {}
    for i in range(0, len(symbols), CHUNK_SIZE):
        batch = symbols[i:i + CHUNK_SIZE]
        logger.info(f"Calculating Sortino Batch [{i//CHUNK_SIZE + 1}/{(len(symbols)//CHUNK_SIZE)+1}]... ({len(batch)} symbols)")
        try:
            batch_map = await batch_fetch_sortino(batch)
            sortino_map.update(batch_map)
        except Exception as e:
            logger.error(f"Sortino batch failed: {e}")
        
        if i + CHUNK_SIZE < len(symbols):
            await asyncio.sleep(2.0) # Rate-limit cooldown
    
    logger.info(f"Sortino metrics finalized for {len(sortino_map)} symbols.")
    
    verified_list = []
    sem = asyncio.Semaphore(5) # Throttle fundamental lookups
    
    async def verify_candidate(c):
        async with sem:
            ticker = c["symbol"]
            sortino = sortino_map.get(ticker, 0.0)
            
            if sortino < effective_hurdle:
                return None
                
            try:
                # Precision Fundamental Verification
                ticker_obj = yf.Ticker(ticker)
                
                # [NEW] Use info first to check for premarket pricing
                info = await asyncio.to_thread(lambda: ticker_obj.info)
                price = info.get("preMarketPrice") or info.get("postMarketPrice") or info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
                
                try:
                    fast = ticker_obj.fast_info
                    volume = fast.last_volume or info.get("volume") or 0
                    m_cap = fast.market_cap or info.get("marketCap") or 0
                    if not price:
                        price = fast.last_price or fast.previous_close or 0.0
                except:
                    # Fallback to standard info if fast_info fails
                    volume = info.get("volume") or 0
                    m_cap = info.get("marketCap") or 0
                
                # Discard stocks less than $1 as requested
                if price < 1.0:
                    return None
                    
                # Float still requires the full info object
                f_shares = info.get("floatShares") or 0
                
                # Check Pillar 1 Constraints
                if not (20_000_000 <= f_shares <= 100_000_000):
                    return None
                if not (300_000_000 <= m_cap <= 2_000_000_000):
                    if m_cap < 200_000_000: return None
                
                return {
                    **c,
                    "price": round(price, 2),
                    "volume": volume,
                    "sortino": round(sortino, 2),
                    "float": f_shares,
                    "market_cap": m_cap,
                    "grade": "A" if sortino >= 3.0 else "B",
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.debug(f"Verification failed for {ticker}: {e}")
                return None

    logger.info(f"Running Fundamental Verification (Pillar 1)...")
    verification_tasks = [verify_candidate(c) for c in candidates]
    verified_candidates = await asyncio.gather(*verification_tasks)
    verified_list = [v for v in verified_candidates if v is not None]

    # 4. Persistence
    combat_list = {
        "updated_at": datetime.now().isoformat(),
        "macro": {
            "tnx_rate": round(tnx_rate, 2),
            "sortino_hurdle": effective_hurdle
        },
        "universe_size": total_count or len(candidates),
        "verified_count": len(verified_list),
        "combat_list": verified_list
    }

    clean_combat_list = sanitize_data(combat_list)

    with open(COMBAT_LIST_PATH, "w", encoding="utf-8") as f:
        json.dump(clean_combat_list, f, indent=4)

    logger.info(f"Combat List synchronized. {len(verified_list)} verified swords in the bunker.")
    return clean_combat_list

async def run_intraday_trawl():
    """
    Periodic lightweight wrapper for the Sortino Sniper Trawl.
    Executes the background sweep with explicit memory configurations to update momentum safely intraday.
    """
    logger.info("Intraday Trawl Initiated: Refreshing Combat List (Checking for momentum breakouts...)")
    try:
        await run_background_trawl({"is_intraday": True})
    except Exception as e:
        logger.error(f"Intraday Trawl execution failed: {e}")

if __name__ == "__main__":
    # Diagnostic entry point
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_background_trawl())
