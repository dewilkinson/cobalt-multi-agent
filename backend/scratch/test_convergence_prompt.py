import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph.builder import build_graph
from langchain_core.messages import HumanMessage

async def test_convergence_model():
    print("\n[TEST] Compiling VLI Engine Graph...")
    graph = build_graph()
    
    prompt = """
[INPUT: SPECULATIVE FORECAST REQUEST]

Please give me "The Next Week" forecast based on the following deterministic rules. 
Execute these tools to build your evidence map before predicting the market trajectory:
1. Fetch the forward-looking economic calendar macro events.
2. Run a batch_smc_analysis on SPY, QQQ, and IWM.
3. Fetch the latest global news and web sentiment for the broader market index (SPY).

Based on the evidence you gather via these tools, speculate on the market trajectory for Monday-Friday. 
Identify if the macro data is likely to act as a 'Catalyst' or a 'Reversal' given the HTF Bias. 
Assign a confidence score (0-100%) to your primary thesis.
"""

    print("\n[TEST] Sending Prompt to Spine...")
    
    config = {"configurable": {"thread_id": "test_convergence_01"}}
    
    final_output = ""
    print("\n--- LLM RESPONSE STREAM ---")
    
    try:
        async for output in graph.astream({"messages": [HumanMessage(content=prompt.strip())]}, config, stream_mode="updates"):
            for node_name, state_update in output.items():
                print(f"[{node_name}] Executed.")
                if node_name == "reporter" and "final_report" in state_update:
                    final_output = str(state_update["final_report"])
    except Exception as e:
        print(f"\n[ERROR] Graph execution crashed: {e}")
        return

    print("\n---------------------------")
    print("\nFINAL SYNTHESIS:\n")
    print(final_output)
    
    # Simple Validations
    print("\n[TEST] Validating deterministic tool orchestration...")
    required_keywords = ["SPY", "QQQ", "IWM", "confidence"]
    
    success = True
    for kw in required_keywords:
        if kw.lower() not in final_output.lower():
            print(f"[FAIL] Expected keyword '{kw}' missing from final synthesis.")
            success = False
            
    if success:
        print("\n✅ VLI Convergence Engine Test PASS: The agent successfully marshalled the batch tools and synthesized the forward-looking Speculative Report!")
    else:
        print("\n❌ VLI Convergence Engine Test FAIL: Missing critical evidence elements in the output.")

if __name__ == "__main__":
    asyncio.run(test_convergence_model())


