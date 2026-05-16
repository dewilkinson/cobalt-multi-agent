import os
from dotenv import load_dotenv
load_dotenv()
import asyncio
from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type
import datetime

async def test_coordinator_logging():
    print("--- RUNNING TELEMETRY UNIT TEST ---")
    
    thinking_mode = False
    
    coord_tier = "reasoning" if os.environ.get("VLI_COORDINATOR_TIER") == "reasoning" else AGENT_LLM_MAP.get("coordinator", "basic")
    actual_tier = coord_tier
    
    if not thinking_mode:
        actual_tier = "basic"
        
    display_model = actual_tier.upper()
    
    try:
        temp_llm = get_llm_by_type(actual_tier)
        model_name = getattr(temp_llm, "model", getattr(temp_llm, "model_name", "unknown"))
    except Exception as e:
        model_name = f"unknown ({e})"
        
    if actual_tier == coord_tier and thinking_mode:
        color_hex = "#4CAF50" # Green
    else:
        color_hex = "#FF9800" # Orange
        
    colored_model = f"[[{model_name}|{color_hex}]]"
    timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
    
    log_str = f"{timestamp} **PHASE_B_EXECUTION:** Coordinator triggered. Model: {display_model} {colored_model}. Context: 11179 chars."
    
    print("1. GENERATED LOG STRING (Sent to VLI_Raw_Telemetry.md):")
    print(f"   {log_str}")
    
    print("\n2. DASHBOARD FRONTEND PROCESSING:")
    import re
    processed = re.sub(r'\[\[([^|]+)\|([^\]]+)\]\]', r'<span style="color: \2;">(\1)</span>', log_str)
    print(f"   {processed}")
    
    print("\n3. ASSERTIONS:")
    if "gemini" in processed.lower() and "span" in processed and "#FF9800" in processed:
        print("   [PASSED]: Model name is dynamically fetched and colored ORANGE due to Thinking Mode being OFF.")
    else:
        print("   [FAILED]")
        
if __name__ == "__main__":
    asyncio.run(test_coordinator_logging())
