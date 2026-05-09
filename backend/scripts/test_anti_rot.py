import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.graph.builder import build_graph

async def test_anti_rot():
    # Construct a simple conversational ping to test bypass
    app = build_graph()
    
    print("\n--- 1. Testing Parser Short-Circuit ---")
    config = {"configurable": {"thread_id": "anti-rot-test-1"}}
    state = {"messages": [("user", "Hello Cobalt. How are you doing today?")]}
    
    final_state = None
    step_count = 0
    transitions = []
    
    async for event in app.astream(state, config, stream_mode="updates"):
        for node_name, node_output in event.items():
            print(f"[{step_count}] Output from Node: {node_name}")
            transitions.append(node_name)
            final_state = node_output
        step_count += 1
        
    print(f"Transitions traced: {transitions}")
    if "reporter" in transitions:
        print(" FAILED: Reporter was invoked! Short-circuit failed.")
    else:
        print(" PASSED: Reporter was bypassed efficiently.")

if __name__ == "__main__":
    asyncio.run(test_anti_rot())
