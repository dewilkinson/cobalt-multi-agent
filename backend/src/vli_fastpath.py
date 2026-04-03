"""
Deterministic Fast-Path Engine for VLI Directives.
Bypasses the Agent Graph for simple market data requests to ensure < 1s latency.
"""

import re
import logging
import asyncio
from typing import Optional, Dict, Any, Union

logger = logging.getLogger(__name__)

async def get_fastpath_response(text: str) -> Optional[str]:
    """
    Attempts to resolve simple price or ticker requests WITHOUT an LLM.
    Returns markdown response if successful, None if fallback to Agent is required.
    """
    try:
        text_upper = text.strip().upper()
        text_clean = text_upper.rstrip("?")
        
        # 1. Regex Matcher for Ticker Patterns
        # Matches: "What is the price of VIX", "$AAPL", "Check TSLA", "Quote for MSFT"
        # Prefix group: OPTIONAL but if present, identifies the intent
        # Ticker group: 1-5 letters
        pattern = r"\$([A-Z]{1,5})|(?:\b(?:PRICE OF|WHAT IS|CHECK|GET|QUOTE FOR|IS THE PRICE FOR)\b\s+)\$?([A-Z]{1,5})"
        match = re.search(pattern, text_upper)
        
        ticker = None
        if match:
            ticker = match.group(1) or match.group(2)
            
        # 2. Guard: Length and Skipwords
        # Skip if too long (likely a research query)
        if not ticker or len(text) > 60:
            return None
            
        skipwords = ["THE", "WHAT", "FOR", "PRICE", "IS", "THAT", "THIS", "AGAIN"]
        if ticker in skipwords:
            return None
            
        # 3. Direct Execution Phase
        logger.info(f"VLI Fast-Path: Triggered direct execution for ticker '{ticker}'")
        
        from src.tools.finance import get_stock_quote
        # Force a fresh fetch (Primary)
        quote_res = await get_stock_quote(ticker=ticker)
        
        if isinstance(quote_res, dict):
            symbol = quote_res.get("symbol", ticker)
            price = float(quote_res.get("price", 0))
            change = float(quote_res.get("change", 0))
            sign = "+" if change >= 0 else ""
            
            # Format a tight, professional snapshot (consistent with Dashboard theme)
            return (
                f"### {symbol} Direct Snapshot\n"
                f"- **Current Price**: `${price:.2f}`\n"
                f"- **Daily Change**: `{sign}{change:.2f}%`\n\n"
                f"*Fast-Path Optimizer: Deterministic tool access utilized (0 Tokens).* "
            )
            
        if isinstance(quote_res, str) and "[ERROR]" not in quote_res:
             return quote_res
             
        logger.warning(f"VLI Fast-Path: Tool returned unexpected result for '{ticker}': {quote_res}")
        return None
        
    except Exception as e:
        logger.warning(f"VLI Fast-Path Failure: {e}")
        return None
