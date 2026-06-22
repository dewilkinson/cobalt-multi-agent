import sys
import re

file_path = "backend/src/tools/finance.py"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Semaphore and Fetch AV implementation
p1 = '''_YF_SEMAPHORE: asyncio.Semaphore | None = None

def _get_yf_semaphore() -> asyncio.Semaphore:'''
r1 = '''_YF_SEMAPHORE: asyncio.Semaphore | None = None

# Safety Protocol: Bound Alpha Vantage Endpoint Rate limits to prevent runaway loops
_AV_SEMAPHORE: asyncio.Semaphore | None = None

def _get_av_semaphore() -> asyncio.Semaphore:
    """Bounded Alpha Vantage API call limit to prevent system-spam (15 concurrent max)"""
    global _AV_SEMAPHORE
    if _AV_SEMAPHORE is None:
        _AV_SEMAPHORE = asyncio.Semaphore(15)
    return _AV_SEMAPHORE

def _get_yf_semaphore() -> asyncio.Semaphore:'''
text = text.replace(p1, r1)

p2 = '''def _fetch_batch_history(tickers: list[str], period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """
    Centralized batched fetcher for Yahoo Finance data.
    Ensures all requests are batched where possible.
    Note: Throttling is now handled by the caller via the _YF_SEMAPHORE.
    """'''

r2 = '''def _fetch_av_history(ticker: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    import os
    import httpx
    from io import StringIO
    
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    if not api_key:
        raise ValueError("[STABILITY] ALPHA_VANTAGE_API_KEY is not defined in the environment!")
        
    mapped_interval = interval
    endpoint = "TIME_SERIES_DAILY_ADJUSTED"
    
    if interval in ["1m", "5m", "15m", "30m", "60m"]:
        mapped_interval = interval.replace("m", "min")
        endpoint = "TIME_SERIES_INTRADAY"
        
    url = f"https://www.alphavantage.co/query?function={endpoint}&symbol={ticker}&datatype=csv&entitlement=delayed&apikey={api_key}"
    
    if endpoint == "TIME_SERIES_INTRADAY":
        url += f"&interval={mapped_interval}"
    else:
        if period in ["1y", "2y", "5y", "10y", "max", "ytd"]:
             url += "&outputsize=full"
             
    try:
        resp = httpx.get(url, timeout=20.0)
        resp.raise_for_status()
        
        if "Error Message" in resp.text or "Information" in resp.text:
            logger.error(f"[AV_FETCH] API Error for {ticker}: {resp.text[:100]}")
            return pd.DataFrame()
            
        df = pd.read_csv(StringIO(resp.text))
        if df.empty or 'timestamp' not in df.columns:
            return pd.DataFrame()
            
        df = df[::-1].reset_index(drop=True)
        
        col_map = {
            "timestamp": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        }
        df.rename(columns=col_map, inplace=True)
        
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            
        return df
    except Exception as e:
        logger.error(f"[AV_FETCH] Critical failure parsing CSV for {ticker}: {e}")
        raise e

def _fetch_batch_history(tickers: list[str], period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """
    Centralized batched fetcher.
    Dynamically routes to Alpha Vantage concurrent pipeline OR YFinance fallback pipeline.
    """'''
text = text.replace(p2, r2)


p3 = '''    # Hand off to specific fetchers
    if is_replay:
        logger.info(f"VLI_REPLAY: Universal delegation for {tickers} (Target Origin: {ref_time})")
        data = _fetch_replay_history(tickers, period, interval, end_date=ref_time)
    else:
        logger.debug(f"[WEB REQUEST] Yahoo Finance fetching {len(mapped_tickers)} tickers: {mapped_tickers}")
        start_time = time.time()
        try:'''

r3 = '''    import os
    provider = os.environ.get("DATA_PROVIDER", "yfinance").lower()

    if is_replay:
        logger.info(f"VLI_REPLAY: Universal delegation for {tickers} (Target Origin: {ref_time})")
        data = _fetch_replay_history(tickers, period, interval, end_date=ref_time)
    elif provider == "alpha_vantage":
        logger.info(f"[AV PARALLEL ENGINE] Extracting {len(mapped_tickers)} tickers concurrently via Alpha Vantage")
        
        async def fetch_av_concurrently(t):
            async with _get_av_semaphore():
                try:
                    df = await asyncio.to_thread(_fetch_av_history, t, period, interval)
                    return t, df
                except Exception as e:
                    logger.error(f"[AV PARALLEL ENGINE] Task failed for {t}: {e}")
                    return t, pd.DataFrame()

        loop = asyncio.get_event_loop()
        tasks = [fetch_av_concurrently(t) for t in mapped_tickers]
        
        try:
            results = asyncio.run(asyncio.gather(*tasks))
        except RuntimeError:
            import nest_asyncio
            nest_asyncio.apply()
            results = asyncio.get_event_loop().run_until_complete(asyncio.gather(*tasks))

        master_dict = {}
        for t, df in results:
            if not df.empty:
                for col in df.columns:
                    master_dict[(col, t)] = df[col]
                    
        data = pd.DataFrame(master_dict) if master_dict else pd.DataFrame()
    else:
        logger.debug(f"[WEB REQUEST] Yahoo Finance fetching {len(mapped_tickers)} tickers: {mapped_tickers}")
        start_time = time.time()
        try:'''
text = text.replace(p3, r3)

p4 = '''def get_stock_quote(ticker: str) -> dict[str, Any]:
    """Get the latest real-time stock quote."""
    logger.debug(f"Fetching stock quote for {ticker}")
    mapped_ticker = _normalize_ticker(ticker)
    
    # [UNIVERSAL_TEMPORAL_INSTRUMENTATION]
    from src.utils.temporal import get_effective_now
    ref_time = get_effective_now()
    now = datetime.now()
    
    if abs((now - ref_time).total_seconds()) > 5:
        # We are in time-travel replay mode. We must fetch historical data matching ref_time, not fast_info.
        df = _fetch_batch_history([mapped_ticker], period="5d", interval="1d")
        if df is None or df.empty:
            return {"error": "Failed to fetch replay data"}
            
        return {
            "price": float(df['Close'].iloc[-1]),
            "changePercent": 0.0,  # Could calculate from previous day, but keeping simple for now
            "volume": float(df['Volume'].iloc[-1]),
            "timestamp": ref_time.isoformat()
        }

    try:
        with _YF_QUOTES_LOCK:'''

r4 = '''def get_stock_quote(ticker: str) -> dict[str, Any]:
    """Get the latest real-time stock quote."""
    import os
    import httpx
    logger.debug(f"Fetching stock quote for {ticker}")
    mapped_ticker = _normalize_ticker(ticker)
    
    # [UNIVERSAL_TEMPORAL_INSTRUMENTATION]
    from src.utils.temporal import get_effective_now
    ref_time = get_effective_now()
    now = datetime.now()
    
    provider = os.environ.get("DATA_PROVIDER", "yfinance").lower()

    if abs((now - ref_time).total_seconds()) > 5:
        # We are in time-travel replay mode. We must fetch historical data matching ref_time, not fast_info.
        df = _fetch_batch_history([mapped_ticker], period="5d", interval="1d")
        if df is None or df.empty:
            return {"error": "Failed to fetch replay data"}
            
        return {
            "price": float(df['Close'].iloc[-1]),
            "changePercent": 0.0,  # Could calculate from previous day, but keeping simple for now
            "volume": float(df['Volume'].iloc[-1]),
            "timestamp": ref_time.isoformat()
        }

    try:
        if provider == "alpha_vantage":
            api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
            if not api_key:
                raise ValueError("[STABILITY] ALPHA_VANTAGE_API_KEY missing")
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={mapped_ticker}&entitlement=delayed&apikey={api_key}"
            resp = httpx.get(url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            
            if "Global Quote" in data and data["Global Quote"]:
                gq = data["Global Quote"]
                return {
                    "price": float(gq.get("05. price", 0)),
                    "changePercent": float(gq.get("10. change percent", "0").replace("%", "")),
                    "volume": float(gq.get("06. volume", 0)),
                    "timestamp": datetime.now().isoformat()
                }

        with _YF_QUOTES_LOCK:'''

text = text.replace(p4, r4)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)
print("done")
