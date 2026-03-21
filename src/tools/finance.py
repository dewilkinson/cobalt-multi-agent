# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
import yfinance as yf
from langchain_core.tools import tool
from typing import Dict, Any, Union

logger = logging.getLogger(__name__)

@tool
def get_stock_quote(ticker: str) -> Union[Dict[str, Any], str]:
    """
    Get current stock quote and OHLC (Open, High, Low, Close) data for a given ticker symbol.
    
    Args:
        ticker: The stock ticker symbol (e.g., 'AAPL', 'NVDA', 'TSLA').
        
    Returns:
        A dictionary containing symbol, price, open, high, low, close, and volume, 
        or an error message if the ticker is invalid.
    """
    logger.info(f"Fetching stock quote for {ticker}")
    try:
        stock = yf.Ticker(ticker)
        # Get historical data for the last 5 days to ensure we get a valid close (handles weekends/holidays)
        data = stock.history(period="5d")
        
        if data.empty:
            return f"Error: No data found for ticker symbol '{ticker}'. Please ensure it is a valid Yahoo Finance ticker."
        
        # Get the most recent trading day's data
        last_row = data.iloc[-1]
        
        return {
            "symbol": ticker.upper(),
            "currency": stock.info.get("currency", "USD"),
            "current_price": round(float(last_row['Close']), 2),
            "open": round(float(last_row['Open']), 2),
            "high": round(float(last_row['High']), 2),
            "low": round(float(last_row['Low']), 2),
            "close": round(float(last_row['Close']), 2),
            "volume": int(last_row['Volume']),
            "date": last_row.name.strftime('%Y-%m-%d')
        }
    except Exception as e:
        logger.error(f"Error in get_stock_quote for {ticker}: {str(e)}")
        return f"Error fetching stock data for '{ticker}': {str(e)}"
