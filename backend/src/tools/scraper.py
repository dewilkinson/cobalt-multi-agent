import asyncio
import logging
import json
import os
import time
import base64
from typing import List, Dict, Any, Optional
from pathlib import Path
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "playwright"
CACHE_FILE = CACHE_DIR / "heatmap_cache.json"
CACHE_TTL = 600  # 10 minutes

# Finviz Futures Categories
FUTURES_TABS = ["INDICES", "ENERGY", "BONDS", "SOFTS", "METALS", "MEATS", "GRAINS", "CURRENCIES"]

# Ticker Mapping for Futures Heatmap
TICKER_MAP = {
    "VIX": "VX",
    "DXY": "DX",
    "USD": "DX",
    "TNX": "ZN",
}

async def _load_cache() -> Dict[str, Any]:
    if not CACHE_FILE.exists():
        return {"timestamp": 0, "data": {}, "screenshot": None, "tiles": {}, "last_target": None}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load heatmap cache: {e}")
        return {"timestamp": 0, "data": {}, "screenshot": None, "tiles": {}, "last_target": None}

async def _save_cache(data: Dict[str, Any], screenshot: Optional[str] = None, tiles: Dict[str, Any] = {}, last_target: Optional[str] = None):
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "data": data,
                "screenshot": screenshot,
                "tiles": tiles,
                "last_target": last_target
            }, f)
    except Exception as e:
        logger.error(f"Failed to save heatmap cache: {e}")

async def fetch_finviz_quotes(symbols: List[str]) -> Dict[str, Any]:
    requested_symbols = [s.upper() for s in symbols]
    target_symbols = [TICKER_MAP.get(s, s) for s in requested_symbols]
    
    cache_entry = await _load_cache()
    now = time.time()
    
    # 1. Warm Cache Check
    if now - cache_entry.get("timestamp", 0) < CACHE_TTL:
        results = {}
        cached_data = cache_entry.get("data", {})
        for s in requested_symbols:
            native_s = TICKER_MAP.get(s, s)
            if native_s in cached_data:
                results[s] = {
                    **cached_data[native_s],
                    "screenshot": cache_entry.get("screenshot"),
                    "tile_coord": cache_entry.get("tiles", {}).get(native_s)
                }
        if len(results) == len(requested_symbols):
            return results

    # 2. Browser Extraction Path
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 1200}
        )
        page = await context.new_page()
        
        extracted_data = {}
        tile_coords = {}
        screenshot_b64 = None
        main_target = requested_symbols[0] if requested_symbols else None
        
        try:
            # 2a. Determine Path: Futures Heatmap (Only if requested symbols are in the Futures Map)
            has_futures = any(s in TICKER_MAP for s in requested_symbols)
            
            if has_futures:
                logger.info("Finviz Scraper: Navigating to Futures Heatmap...")
                await page.goto("https://finviz.com/futures.ashx", wait_until="commit", timeout=15000)
                await asyncio.sleep(1) # Stabilization wait for grid rendering
            
            async def extract_visible_tiles(data_dict, coord_dict):
                grid = await page.query_selector("div.grid")
                grid_bbox = await grid.bounding_box() if grid else {"x":0, "y":0}
                tiles = await page.query_selector_all("a[href*='t=']")
                for tile in tiles:
                    try:
                        href = await tile.get_attribute("href")
                        if "t=" in href:
                             sym_p = href.split("t=")[1].split("&")[0].upper()
                             if sym_p not in FUTURES_TABS:
                                 # [ROBUST EXTRACTION] Find Price and Change by numeric/symbol patterns
                                 divs = await tile.query_selector_all("div")
                                 p_val, c_val = 0.0, 0.0
                                 import re
                                 for d in divs:
                                     txt = (await d.inner_text()).strip()
                                     if not txt: continue
                                     # Case 1: Percentage Change or Yield (Has % sign)
                                     if "%" in txt:
                                         try:
                                             clean_val = txt.replace("%", "").replace("+", "").replace(",", "")
                                             val = float(clean_val)
                                             # [ROBUST] For Bond Yields, the %-field is actually the price
                                             if sym_p in ["TNX", "TYX", "FVX"]:
                                                 p_val = val
                                             else:
                                                 c_val = val
                                         except: pass
                                     # Case 2: Price (Numeric patterns, potentially with $)
                                     elif re.search(r"^\$?\d{1,3}(,\d{3})*(\.\d+)?$", txt):
                                         try:
                                             clean_p = txt.replace("$", "").replace(",", "")
                                             # Only assign to p_val if it hasn't been set by yield logic
                                             if p_val == 0:
                                                 p_val = float(clean_p)
                                         except: pass
                                 
                                 if p_val != 0 or c_val != 0:
                                     data_dict[sym_p] = {
                                         "price": p_val,
                                         "change": c_val,
                                         "source": "finviz_heatmap"
                                     }
                                     bbox = await tile.bounding_box()
                                     if bbox and grid_bbox:
                                         coord_dict[sym_p] = {"x": bbox["x"] - grid_bbox["x"], "y": bbox["y"] - grid_bbox["y"], "w": bbox["width"], "h": bbox["height"]}
                    except: continue

            await extract_visible_tiles(extracted_data, tile_coords)
            
            grid_el = await page.query_selector("div.grid")
            if grid_el:
                screenshot_b64 = base64.b64encode(await grid_el.screenshot()).decode("utf-8")

            # Tab Cycle if needed
            if any(ts not in extracted_data for ts in target_symbols):
                for tab in FUTURES_TABS:
                    tab_btn = await page.query_selector(f"a[href*='t={tab}']")
                    if tab_btn:
                        await tab_btn.click()
                        await asyncio.sleep(1)
                        await extract_visible_tiles(extracted_data, tile_coords)
                        if all(ts in extracted_data for ts in target_symbols): break

            else:
                logger.info("Finviz Scraper: Skipping Heatmap (No futures detected in request). Proceeding to Screener.")
                
        except Exception as e:
            logger.error(f"Finviz Scraper Heatmap failed: {e}")

        # 2b. Screener Fallback (Standard Stocks)
        missing = [s for s in requested_symbols if TICKER_MAP.get(s, s) not in extracted_data]
        if missing:
            try:
                # Use wait_until="commit" for maximum speed on the table extraction
                await page.goto(f"https://finviz.com/screener.ashx?v=152&t={','.join(missing)}", wait_until="commit", timeout=15000)
                rows = await page.query_selector_all("table.screener-table tr.screener-row")
                for row in rows:
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 10:
                        ticker = (await cells[1].inner_text()).strip().upper()
                        extracted_data[ticker] = {"price": float((await cells[9].inner_text()).replace(",", "")), "volume": int((await cells[8].inner_text()).replace(",", "")), "source": "finviz_screener"}
            except Exception as e: logger.error(f"Finviz Scraper Screener failed: {e}")

        await browser.close()
        results = {}
        for s in requested_symbols:
            native_s = TICKER_MAP.get(s, s)
            if native_s in extracted_data:
                results[s] = {**extracted_data[native_s], "screenshot": screenshot_b64, "tile_coord": tile_coords.get(native_s)}
        return results

async def get_macro_prices(symbols: List[str]) -> List[Dict[str, Any]]:
    """VLI specific wrapper for batch symbol price retrieval with yfinance fallback."""
    try:
        raw_data = await fetch_finviz_quotes(symbols)
        results = []
        import yfinance
        
        for sym in symbols:
            q = raw_data.get(sym.upper(), {})
            price = q.get("price", 0)
            change = q.get("change", 0)
            
            # [FALLBACK] If price is missing or if it's a Bond Yield (TNX/TYX/FVX) or Currency (EURUSD)
            if price == 0 or sym.upper() in ["TNX", "TYX", "FVX", "EURUSD", "EUR/USD"]:
                try:
                    from .finance import _normalize_ticker
                    norm = _normalize_ticker(sym)
                    t_obj = yfinance.Ticker(norm)
                    
                    # Try fast_info first
                    try:
                        price = t_obj.fast_info.last_price
                        change = ((t_obj.fast_info.last_price / t_obj.fast_info.previous_close) - 1) * 100 if t_obj.fast_info.previous_close else 0.0
                    except:
                        # [RESONANCE] Deep fallback for yields/currencies using historical data
                        hist = t_obj.history(period="2d")
                        if not hist.empty:
                            price = hist['Close'].iloc[-1]
                            if len(hist) > 1:
                                change = ((price / hist['Close'].iloc[-2]) - 1) * 100
                    
                    if price is not None and price != 0:
                        logger.info(f"VLI Scraper Fallback: {sym} -> {price:.2f} (via YFinance - {norm})")
                    else:
                        price = 0
                        change = 0
                except Exception as fe:
                    logger.debug(f"Fallback failed for {sym}: {fe}")
            
            results.append({
                "symbol": sym,
                "price": price,
                "change": change,
                "volume": q.get("volume", 0),
                "color": "gray" # Reverting to neutral Antigravity color scheme
            })
        return results
    except Exception as e:
        logger.error(f"VLI Scraper: Failed to fetch macro prices: {e}")
        return []

def get_latest_ux_data(symbol: str) -> Dict[str, Any]:
    if not CACHE_FILE.exists(): return {"active": False}
    try:
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
            now = time.time()
            if now - cache.get("timestamp", 0) > 600: return {"active": False}
            target = symbol if symbol else cache.get("last_target", "VIX")
            native_s = TICKER_MAP.get(target.upper(), target.upper())
            return {
                "active": True,
                "image": cache.get("screenshot"),
                "target": target,
                "highlight": cache.get("tiles", {}).get(native_s)
            }
    except: pass
    return {"active": False}
