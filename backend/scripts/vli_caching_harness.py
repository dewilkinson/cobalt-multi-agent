#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
import pandas as pd
from unittest.mock import patch
from colorama import init, Fore, Back, Style

# Initialize colorama for Windows support
init(autoreset=True)

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.finance import get_symbol_history_data
from src.tools.shared_storage import GLOBAL_CONTEXT
from src.graph.nodes.coordinator import coordinator_node

# Constants for colors (using blocks for high visibility)
PASS = f"{Style.BRIGHT}{Fore.WHITE}{Back.GREEN}  PASS  {Style.RESET_ALL}"
FAIL = f"{Style.BRIGHT}{Fore.WHITE}{Back.RED}  FAIL  {Style.RESET_ALL}"
INFO = f"{Fore.CYAN}{Style.BRIGHT}[INFO]{Style.RESET_ALL}"
STEP = f"{Fore.YELLOW}{Style.BRIGHT}[STEP]{Style.RESET_ALL}"

def print_header(title):
    print("\n" + "="*60)
    print(f"{Fore.MAGENTA}{Style.BRIGHT}{title.upper()}{Style.RESET_ALL}")
    print("="*60)

async def run_harness():
    print_header("Cobalt VLI Caching Test Harness")
    
    # 1. Setup
    print(f"{INFO} Cleaning Global Context...")
    GLOBAL_CONTEXT.clear()
    
    # 2. Mock Stock Retrieval Test
    print(f"{STEP} 1. Testing Mock Stock Retrieval (MOCK_TICKER)...")
    mock_df = pd.DataFrame({
        ("MOCK_TICKER", "Close"): {0: 100.0},
        ("MOCK_TICKER", "High"): {0: 105.0},
        ("MOCK_TICKER", "Low"): {0: 95.0},
        ("MOCK_TICKER", "Volume"): {0: 1000}
    })
    mock_df.columns = pd.MultiIndex.from_tuples(mock_df.columns)
    
    with patch("src.tools.finance._fetch_batch_history", return_value=mock_df):
        await get_symbol_history_data.ainvoke({"symbols": ["MOCK_TICKER"]})
    
    if "cached_tickers" in GLOBAL_CONTEXT and "MOCK_TICKER" in GLOBAL_CONTEXT["cached_tickers"]:
        print(f"{PASS} MOCK_TICKER successfully registered in Global Cache.")
    else:
        print(f"{FAIL} MOCK_TICKER failed to register in Global Cache.")
        return

    # 3. Real Stock Retrieval Test
    print(f"{STEP} 2. Testing Real Stock Retrieval (QQQ)...")
    try:
        # Use a real fetch but with a small period to be fast
        await get_symbol_history_data.ainvoke({"symbols": ["QQQ"], "period": "1d", "interval": "1h"})
        if "QQQ" in GLOBAL_CONTEXT.get("cached_tickers", set()):
            print(f"{PASS} Real ticker QQQ successfully registered in Global Cache.")
        else:
            print(f"{FAIL} Real ticker QQQ missing from Global Cache after fetch.")
    except Exception as e:
        print(f"{FAIL} Real retrieval failed with error: {e}")

    # 4. Coordinator Cache-Awareness Test
    print(f"{STEP} 3. Testing Coordinator Cache-Awareness...")
    # Pre-seed with something unique
    GLOBAL_CONTEXT.setdefault("cached_tickers", set()).add("COBALT_VLI_ACTIVE")
    
    mock_state = {"messages": [], "current_plan": None}
    # Mock apply_prompt_template to capture the context sent to the LLM
    with patch("src.graph.nodes.coordinator.apply_prompt_template") as mock_prompt:
        mock_prompt.return_value = [] # Just return empty list
        # Mock get_llm_by_type to avoid real LLM calls
        with patch("src.graph.nodes.coordinator.get_llm_by_type") as mock_llm:
            # Setup mock LLM with structured output
            mock_llm_instance = mock_llm.return_value
            mock_structured = mock_llm_instance.bind_tools.return_value.with_structured_output.return_value
            mock_structured.invoke.return_value = {"steps": []} # Mock plan
            
            try:
                coordinator_node(mock_state, {})
                
                # Check what was passed to apply_prompt_template
                args, _ = mock_prompt.call_args
                passed_state = args[1]
                cached_str = passed_state.get("CACHED_TICKERS", "")
                
                if "COBALT_VLI_ACTIVE" in cached_str and "QQQ" in cached_str:
                    print(f"{PASS} Coordinator successfully detected Global Cache: {cached_str}")
                else:
                    print(f"{FAIL} Coordinator failed to detect tickers in Global Cache. Found: {cached_str}")
            except Exception as e:
                print(f"{FAIL} Coordinator node execution died: {e}")

    print_header("Harness Execution Complete")

if __name__ == "__main__":
    asyncio.run(run_harness())
