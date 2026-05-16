import os
from dotenv import load_dotenv
load_dotenv()

import asyncio
from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type

async def main():
    coord_tier = AGENT_LLM_MAP.get("coordinator", "basic")
    actual_tier = coord_tier
    
    # Simulate user override
    actual_tier = "basic"
        
    display_model = actual_tier.upper()
    if os.environ.get("BYPASS_REASONING_MODEL", "false").lower() == "true":
        display_model = f"{actual_tier.upper()} [BYPASSED -> FLASH]"
        
    try:
        temp_llm = get_llm_by_type(actual_tier)
        model_name = getattr(temp_llm, "model", getattr(temp_llm, "model_name", "unknown"))
    except Exception as e:
        model_name = f"error: {e}"
        
    if actual_tier == coord_tier:
        colored_model = f'<span style="color: #4CAF50;">({model_name})</span>' # Green
    else:
        colored_model = f'<span style="color: #FF9800;">({model_name})</span>' # Orange
        
    log_str = f"**PHASE_B_EXECUTION:** Coordinator triggered. Model: {display_model} {colored_model}. Context: 123 chars."
    print("RAW LOG STRING:", log_str)
    
if __name__ == "__main__":
    asyncio.run(main())
