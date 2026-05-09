import asyncio
import os
import sys
import logging

# Setup environment
sys.path.append(os.getcwd())
os.environ["COBALT_AI_ON"] = "True"

from src.llms.llm import get_llm_by_type
from src.prompts.template import apply_prompt_template
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Mock SMC Specialist Output
MOCK_SMC_DATA = """
## MTF SMC Alignment Scan: GOOGL (Apex 500 Scanner)

- **OHLC**: O: `140.20` | H: `142.50` | L: `139.80` | C: `141.90` | V: `18500000`
- **State**:  **Break of Structure (BOS)** confirmed on 1h TF.
- **Order Blocks**: 3 mapping (Bullish OB at 139.50).
- **FVGs**: 2 Bullish FVGs detected.
- **Apex Authorization**: STRIKE (Alignment confirmed on 1d/1h).

[INSTITUTIONAL_NOTE]: Volume profile indicates heavy accumulation at the 140 base.
"""

async def repro():
    print("=== VLI SDK Block Reproduction (REASONING MODEL) ===")
    
    # Use 'reasoning' to match VLI Spine default
    llm = get_llm_by_type("reasoning")
    print(f"Testing with Model: {getattr(llm, 'model_name', getattr(llm, 'model', 'Unknown'))}")
    
    state = {
        "messages": [
            HumanMessage(content="Run an SMC analysis for GOOGL."),
            AIMessage(content="[Agent invoked tool(s): smc_analyst]"),
            HumanMessage(content=f"[System: Tool 'smc_analyst' Returned]:\n{MOCK_SMC_DATA}"),
            HumanMessage(content=f"[System: Tool 'metrics_scanner' Returned]:\nSharp > 1.5")
        ],
        "locale": "en-US"
    }
    
    print("Applying 'reporter' template...")
    messages = apply_prompt_template("reporter", state)
    
    print("Invoking Model...")
    try:
        response = await llm.ainvoke(messages)
        
        print(f"\n--- Response Content ---")
        print(f"Type: {type(response.content)}")
        print(f"Value: '{response.content}'")
        
        print(f"\n--- Metadata ---")
        import json
        meta = getattr(response, "response_metadata", {})
        print(json.dumps(meta, indent=2))
        
        # Check for safety blocks or empty payloads
        if not response.content or response.content == "[]" or response.content == []:
            print("\n!!! REPRODUCED: Blocked by SDK (Empty Content) !!!")
        else:
            print("\nSUCCESS: Model returned content.")
            
    except Exception as e:
        print(f"Invocation Failed: {e}")

if __name__ == "__main__":
    asyncio.run(repro())
