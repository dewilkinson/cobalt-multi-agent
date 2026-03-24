# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
import asyncio
import yfinance as yf
from langchain_core.tools import tool
from typing import Dict, Any, Union

logger = logging.getLogger(__name__)

@tool
async def get_stock_quote(ticker: str) -> Union[Dict[str, Any], str]:
    """
    Get current stock quote and OHLC (Open, High, Low, Close) data for a given ticker symbol.
    
    Args:
        ticker: The stock ticker symbol (e.g., 'AAPL', 'NVDA', 'TSLA').
        
    Returns:
        A dictionary containing symbol, price, open, high, low, close, and volume, 
        or an error message if the ticker is invalid.
    """
    logger.info(f"Fetching stock quote for {ticker}")
    
    # Inner synchronous fetching function to be run in a separate thread
    def fetch_data(ticker_symbol: str):
        logger.info(f"Initializing ticker in thread for '{ticker_symbol}'...")
        stock = yf.Ticker(ticker_symbol)
        connection_info = f"Requesting '{ticker_symbol}' from Yahoo Finance API (yfinance v2)..."
        params = {"ticker": ticker_symbol, "period": "5d", "interval": "1d"}
        
        logger.info("Fetching history in thread...")
        data = stock.history(period="5d")
        
        logger.info("History fetched in thread.")
        if data.empty:
            return f"[ERROR]: No data found for ticker '{ticker_symbol}'.\n[CONN_INFO]: {connection_info}"
        
        last_row = data.iloc[-1]
        raw_payload = data.tail(1).to_json(orient="records")
        
        logger.info("Fetching currency...")
        try:
            # Avoid notoriously slow stock.info which can hang indefinitely.
            currency = stock.fast_info.get("currency", "USD") if hasattr(stock, "fast_info") else "USD"
        except Exception:
            currency = "USD"
        logger.info(f"Currency fetched: {currency}")
        
        report = f"""
[TECHNICAL_LOG]
Status: SUCCESS
Connection: {connection_info}
Parameters: {params}

[API_PAYLOAD]
{raw_payload}

[OHLC_DATA]
Symbol: {ticker_symbol.upper()}
Currency: {currency}
Date: {last_row.name.strftime('%Y-%m-%d')}
Open: {float(last_row['Open']):.2f}
High: {float(last_row['High']):.2f}
Low: {float(last_row['Low']):.2f}
Close: {float(last_row['Close']):.2f}
Current: {float(last_row['Close']):.2f}
Volume: {int(last_row['Volume'])}
"""
        return report.strip()

    try:
        # Implementing a 15-second timeout for the synchronous yfinance data fetching
        result = await asyncio.wait_for(asyncio.to_thread(fetch_data, ticker), timeout=15.0)
        return result
    except asyncio.TimeoutError:
        logger.error(f"Timeout while fetching stock quote for {ticker} after 15 seconds")
        return f"[ERROR]: Timeout (15s) while attempting to fetch '{ticker}' from Yahoo Finance API."
    except Exception as e:
        logger.error(f"Error in get_stock_quote for {ticker}: {str(e)}")
        return f"[ERROR]: {str(e)}\n[CONN_INFO]: Attempted connection to Yahoo Finance for {ticker}"

