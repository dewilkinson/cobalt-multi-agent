import logging
import asyncio
from typing import Any
from datetime import datetime
from langchain_core.tools import tool
import yfinance
import httpx
import os
from src.services.datastore import DatastoreManager

logger = logging.getLogger(__name__)

@tool
async def get_ticker_news(ticker: str) -> str:
    """
    Scout Primitive: Fetches and categorizes the latest news for a specific ticker.
    Implements Alpha Vantage Institutional Intelligence if enabled.
    """
    t = ticker.upper()
    
    cached = DatastoreManager.get_artifact(t, "news", "latest")
    if cached:
        logger.info(f"[NEWS] Cache hit for {t}")
        return cached.get("data", "")

    report = [f"## Latest Institutional News & Sentiment: {t}", ""]
    headlines = []
    
    provider = os.environ.get("DATA_PROVIDER", "yfinance").lower()
    success = False

    try:
        if provider == "alpha_vantage":
            api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
            if not api_key:
                raise ValueError("[STABILITY] ALPHA_VANTAGE_API_KEY missing")
                
            url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={t}&apikey={api_key}&limit=20"
            resp = httpx.get(url, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            
            feed = data.get("feed", [])
            if feed:
                report.append("### Alpha Vantage Intelligence Scout")
                for item in feed:
                    # Filter low relevance news using dynamic threshold
                    try:
                        relevance_threshold = float(os.environ.get("STRICTNESS_AV_RELEVANCE", "0.5"))
                    except:
                        relevance_threshold = 0.5
                        
                    rel_score = 0.0
                    tik_score = 0.0
                    for ts in item.get("ticker_sentiment", []):
                        if ts.get("ticker") == t:
                            rel_score = float(ts.get("relevance_score", 0))
                            tik_score = float(ts.get("ticker_sentiment_score", 0))
                            break
                            
                    if rel_score > relevance_threshold:
                        title = item.get('title', 'No Title')
                        headlines.append(title)
                        source = item.get('source', '')
                        url = item.get('url', '')
                        summary = item.get('summary', '')[:200]
                        label = item.get('overall_sentiment_label', 'Neutral')
                        
                        report.append(f"- **{title}** ({source}) | Polarity: {tik_score} ({label})")
                        report.append(f"  > {summary}...")
                        report.append(f"  [Source]({url})")
                        
                success = True
                logger.info(f"[NEWS] Successfully fetched Alpha Vantage Sentiment for {t}")
                
    except Exception as e:
        logger.warning(f"[NEWS] Alpha Vantage fetch for {t} failed, falling back to basic YFinance: {e}")
        
    if not success:
        try:
            ticker_obj = yfinance.Ticker(t)
            news_items = ticker_obj.news[:5]
            
            if not news_items:
                return f"No recent news found for {t}."
                
            report.append("### Basic Press Releases (YFinance Fallback)")
            for item in news_items:
                title = item.get("title", "")
                publisher = item.get("publisher", "Unknown")
                link = item.get("link", "#")
                headlines.append(title)
                report.append(f"- **{title}** ({publisher})")
                report.append(f"  [Read More]({link})")
        except Exception as e:
            logger.error(f"YFinance fallback failed for {t}: {e}")
            return f"[ERROR]: Failed to fetch news for {t}: {e}"

    full_report = "\\n".join([str(r) for r in report])
    
    try:
        impact_data = await _analyze_news_impact(t, headlines)
        final_report = await _resolve_contradictions(t, full_report)
        
        DatastoreManager.store_artifact(
            t, "news", "latest", final_report, 
            ttl=impact_data.get("ttl_sec", 3600),
            persist=True
        )
        return final_report
    except Exception as e:
        logger.error(f"News fetch finalization failed for {t}: {e}")
        return f"[ERROR]: Failed to finalize news for {t}: {e}"

async def _analyze_news_impact(ticker: str, headlines: list[str]) -> dict[str, Any]:
    text = " ".join([str(h) for h in headlines]).upper()
    if any(k in text for k in ["BREAKING", "FLASH", "HALTED", "SPIKE", "CRASH"]):
        return {"impact": "FLASH", "ttl_sec": 60}
    if any(k in text for k in ["ACQUISITION", "MERGER", "CEO", "BANKRUPTCY", "REGULATORY"]):
        return {"impact": "STRUCTURAL", "ttl_sec": 2592000}
    return {"impact": "DAILY", "ttl_sec": 86400}

async def _resolve_contradictions(ticker: str, new_report: str) -> str:
    old_report_obj = DatastoreManager.get_artifact(ticker, "news", "latest")
    if not old_report_obj:
        return new_report
        
    old_report = old_report_obj.get("data", "")
    if not old_report:
        return new_report
        
    conflicts = [
        ("BULLISH", "BEARISH"),
        ("GROWTH", "CONTRACTION"),
        ("ACQUIRED", "DENIED"),
        ("EXPANSION", "REDUCTION")
    ]
    
    resolved_report = new_report
    new_upper = new_report.upper()
    old_upper = old_report.upper()
    
    for term1, term2 in conflicts:
        if (term1 in new_upper and term2 in old_upper) or (term2 in new_upper and term1 in old_upper):
            conflict_term = term2 if term1 in new_upper else term1
            resolved_report = f"> [!WARNING]\\n> **SUPERSEDENCE DETECTED**: New data conflicts with prior {conflict_term} outlook.\\n\\n" + resolved_report
            break
            
    return resolved_report
