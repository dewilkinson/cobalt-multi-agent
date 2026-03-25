# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
import json

def get_analyst_keywords():
    """
    Load analyst keywords from the configuration file.
    These keywords trigger mandatory routing to the Analyst agent.
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        "agents", 
        "definitions", 
        "analyst_keywords.json"
    )
    
    # Default keywords if file is missing
    default_keywords = ["SMC", "EMA", "RSI", "MACD", "ATR", "BOS", "FVG", "CHoCH", "Liquidity", "Order Block"]
    
    if not os.path.exists(config_path):
        return default_keywords
        
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
            return data.get("keywords", default_keywords)
    except Exception:
        return default_keywords
