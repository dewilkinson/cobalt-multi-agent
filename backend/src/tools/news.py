import logging
import asyncio
from typing import Any
from datetime import datetime
from langchain_core.tools import tool
import yfinance
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import os
from src.services.datastore import DatastoreManager
from src.utils.temporal import get_effective_now

logger = logging.getLogger(__name__)

def _sanitize_text(text: str) -> str:
    if not text:
        return ""
    return text.encode("ascii", "ignore").decode("ascii")

@tool
async def get_ticker_news(subject: str = "", ticker: str = "", refresh: bool = False) -> str:
    """
    Scout Primitive: Fetches and categorizes the latest news for a specific stock ticker OR a general topic (e.g. 'Iran War').
    Implements Alpha Vantage Institutional Intelligence if enabled, falling back to Web Search for generic subjects.
    You must provide EITHER 'subject' or 'ticker'.
    """
    subject = subject or ticker
    if not subject:
        return "[ERROR] Missing subject or ticker argument."
    t = subject.upper().strip(".,;:!")
    is_ticker = len(t) <= 6 and " " not in t
    
    if not refresh:
        cached = DatastoreManager.get_artifact(t, "news", "latest")
        if cached:
            logger.info(f"[NEWS] Cache hit for {t}")
            return cached.get("data", "")

    report = [f"## Latest Institutional News & Sentiment: {t}", ""]
    headlines = []
    raw_news_items = []
    
    ref_time = get_effective_now()

    provider = os.environ.get("DATA_PROVIDER", "yfinance").lower()
    success = False

    try:
        if is_ticker and provider == "alpha_vantage":
            api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
            if not api_key:
                raise ValueError("[STABILITY] ALPHA_VANTAGE_API_KEY missing")
                
            url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={t}&apikey={api_key}&entitlement=realtime&limit=20"
            @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
            def _fetch_av_news():
                r = httpx.get(url, timeout=45.0)
                r.raise_for_status()
                if "Error Message" in r.text or "Information" in r.text:
                    raise RuntimeError("Alpha Vantage Rate Limit or API Error")
                return r
            resp = await asyncio.to_thread(_fetch_av_news)
            data = resp.json()
            
            feed = data.get("feed", [])
            if feed:
                report.append("### Alpha Vantage Intelligence Scout")
                for item in feed:
                    # [TEMPORAL_CUTOFF] Ensure no future-leakage during replay
                    time_published = item.get("time_published", "")
                    if time_published:
                        try:
                            item_dt = datetime.strptime(time_published, "%Y%m%dT%H%M%S")
                            if item_dt > ref_time:
                                continue
                        except Exception:
                            pass

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
                        title = _sanitize_text(item.get('title', 'No Title'))
                        headlines.append(title)
                        source = _sanitize_text(item.get('source', ''))
                        url = item.get('url', '')
                        summary = _sanitize_text(item.get('summary', ''))[:200]
                        label = item.get('overall_sentiment_label', 'Neutral')
                        
                        report.append(f"- **{title}** ({source}) | Polarity: {tik_score} ({label})")
                        report.append(f"  > {summary}...")
                        report.append(f"  [Source]({url})")
                        
                        raw_news_items.append(f"Headline {title}\nSource: {source or url}\nRelevance: {rel_score}")
                        
                success = True
                logger.info(f"[NEWS] Successfully fetched Alpha Vantage Sentiment for {t}")
                
    except Exception as e:
        logger.warning(f"[NEWS] Alpha Vantage fetch for {t} failed or skipped, falling back: {e}")
        
    if not success and is_ticker:
        try:
            @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
            def _fetch_yf_news():
                return yfinance.Ticker(t).news[:5]
            news_items = await asyncio.wait_for(asyncio.to_thread(_fetch_yf_news), timeout=15.0)
            
            if not news_items:
                logger.warning(f"[NEWS] YFinance found no news for {t}, dropping to general web search.")
            else:
                report.append("### Basic Press Releases (YFinance Fallback)")
                for item in news_items:
                    # [TEMPORAL_CUTOFF] Ensure no future-leakage during replay
                    pub_time = item.get("providerPublishTime", 0)
                    if pub_time and isinstance(pub_time, int):
                        if pub_time > ref_time.timestamp():
                            continue

                    title = _sanitize_text(item.get("title", ""))
                    publisher = _sanitize_text(item.get("publisher", "Unknown"))
                    link = item.get("link", "#")
                    headlines.append(title)
                    report.append(f"- **{title}** ({publisher})")
                    report.append(f"  [Read More]({link})")
                    
                    raw_news_items.append(f"Headline {title}\nSource: {publisher} or {link}\nRelevance: N/A")
                success = True
        except Exception as e:
            logger.error(f"YFinance fallback failed for {t}: {e}")

    # Final fallback for generic subjects or failed ticker lookups
    from src.tools.search import get_web_search_tool
    if not success:
        try:
            logger.info(f"[NEWS] Executing General Web Search for subject: {subject}")
            search_tool = get_web_search_tool(max_search_results=5)
            # Use ainvoke with strict timeout to prevent hanging the event loop
            @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
            async def _do_search():
                query_suffix = f" before:{ref_time.strftime('%Y-%m-%d')}"
                query_str = f"{subject} latest breaking financial news{query_suffix}"
                return await asyncio.wait_for(search_tool.ainvoke(query_str), timeout=30.0)
            search_out = await _do_search()
            
            report.append(f"### Web Search Intelligence")
            if isinstance(search_out, list):
                for item in search_out:
                    if isinstance(item, dict):
                        title = _sanitize_text(item.get("title", ""))
                        content = _sanitize_text(item.get("content", ""))
                        link = item.get("url", "#")
                        snippet = content[:250].replace('\n', ' ')
                        report.append(f"- **{title}**\n  > {snippet}...\n  [Source]({link})")
                        raw_news_items.append(f"Headline: {title}\nSnippet: {snippet}...\nSource: {link}")
            else:
                report.append(str(search_out)[:500])
                raw_news_items.append(f"Web Search Results:\n{str(search_out)[:500]}")
            success = True
        except Exception as e:
            logger.error(f"Web Search fallback failed for {subject}: {e}")
            error_msg = f"<span style='color:var(--ruby-red); font-weight:bold;'>[ERROR] NEWS RETRIEVAL FAILED FOR {subject}: {e}</span>"
            return error_msg

    if is_ticker:
        try:
            logger.info(f"[NEWS] Executing Social Media Search for ticker: {t}")
            search_tool_social = get_web_search_tool(max_search_results=3)
            social_sources = os.environ.get("SOCIAL_SOURCES", "twitter.com, reddit.com").split(",")
            report.append(f"### Social Media Pulse")
            query_suffix = f" before:{ref_time.strftime('%Y-%m-%d')}"
            for source in social_sources:
                source = source.strip()
                if not source: continue
                query = f"site:{source} {t} stock sentiment{query_suffix}"
                @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
                async def _do_social_search(q):
                    return await asyncio.wait_for(search_tool_social.ainvoke(q), timeout=25.0)
                try:
                    social_out = await _do_social_search(query)
                    report.append(f"#### {source.capitalize()}")
                    if isinstance(social_out, list):
                        for item in social_out:
                            if isinstance(item, dict):
                                title = _sanitize_text(item.get("title", ""))
                                content = _sanitize_text(item.get("content", ""))
                                # Filter out obvious platform login boilerplate
                                if any(b in content for b in ["Sign in", "Log In", "Create account", "Forgot password"]):
                                    continue
                                snippet = content[:250].replace('\n', ' ')
                                report.append(f"- **{title}**: {snippet}...")
                                raw_news_items.append(f"Social Post: {title}\nSnippet: {snippet}...\nSource: {source}")
                    else:
                        report.append(str(social_out)[:500])
                        raw_news_items.append(f"Social Results ({source}):\n{str(social_out)[:500]}")
                except asyncio.TimeoutError:
                    logger.warning(f"Social search timeout for {source}")
                    report.append(f"#### {source.capitalize()}\nData Unavailable (Timeout)")
        except Exception as e:
            logger.error(f"Social Media search failed for {t}: {e}")

    full_report = "\n".join([str(r) for r in report])
    
    try:
        impact_data = await _analyze_news_impact(t, headlines)
        final_report = await _resolve_contradictions(t, full_report)
        
        DatastoreManager.store_artifact(
            t, "news", "latest", final_report, 
            ttl=impact_data.get("ttl_sec", 3600),
            persist=True
        )
        
        raw_news_str = "\n\n".join(raw_news_items) if raw_news_items else "No Information Found."
        DatastoreManager.store_artifact(
            t, "news_raw", "latest", raw_news_str,
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
            resolved_report = f"> [!WARNING]\n> **SUPERSEDENCE DETECTED**: New data conflicts with prior {conflict_term} outlook.\n\n" + resolved_report
            break
            
    return resolved_report

@tool
async def get_macro_news(refresh: bool = False) -> str:
    """
    Macro Primitive: Fetches and categorizes the latest institutional macroeconomic news headlines.
    Uses Alpha Vantage economy_macro topics.
    """
    if not refresh:
        cached = DatastoreManager.get_artifact("MACRO", "news", "latest")
        if cached:
            logger.info(f"[NEWS] Cache hit for MACRO NEWS")
            return cached.get("data", "")

    report = ["## Latest Institutional Macroeconomic News & Sentiment", ""]
    headlines = []
    
    ref_time = get_effective_now()
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    
    success = False
    if api_key:
        try:
            url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&topics=economy_macro&apikey={api_key}&entitlement=realtime&limit=10"
            @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
            def _fetch_av_macro_news():
                r = httpx.get(url, timeout=45.0)
                r.raise_for_status()
                if "Error Message" in r.text or "Information" in r.text:
                    raise RuntimeError("Alpha Vantage Rate Limit or API Error")
                return r
            resp = await asyncio.to_thread(_fetch_av_macro_news)
            data = resp.json()
            
            feed = data.get("feed", [])
            if feed:
                report.append("### Alpha Vantage Macro Intelligence")
                for item in feed:
                    time_published = item.get("time_published", "")
                    if time_published:
                        try:
                            item_dt = datetime.strptime(time_published, "%Y%m%dT%H%M%S")
                            if item_dt > ref_time:
                                continue
                        except Exception:
                            pass
                            
                    title = item.get("title", "")
                    source = item.get("source", "Unknown")
                    url_link = item.get("url", "#")
                    summary = item.get("summary", "")[:200] + "..."
                    
                    headlines.append(title)
                    report.append(f"- **{title}** ({source})")
                    report.append(f"  *Summary*: {summary}")
                    report.append(f"  [Read More]({url_link})")
                success = True
        except Exception as e:
            logger.error(f"Alpha Vantage Macro news failed: {e}")
            
    if not success:
        logger.warning("[NEWS] Alpha Vantage macro failed, dropping to general web search.")
        from src.tools.search import get_web_search_tool
        try:
            search_tool = get_web_search_tool(max_results=5)
            search_query = f"global macro economic market news today {ref_time.strftime('%Y-%m-%d')}"
            search_res = await search_tool.ainvoke({"query": search_query})
            
            report.append("### Global Macro Web Intelligence (Fallback)")
            report.append(search_res)
        except Exception as e:
            report.append(f"Failed to retrieve macro news: {e}")

    final_report = "\n".join(report)
    DatastoreManager.store_artifact("MACRO", "news", "latest", {"data": final_report, "headlines": headlines})
    return final_report

