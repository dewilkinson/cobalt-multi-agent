
# VLI Vision Specialist Diagnostic - SMC 7-Panel Audit
import asyncio
import base64
import os
from langchain_core.messages import HumanMessage
from src.graph.nodes.vision_specialist import vision_specialist_node

async def run_vision_test():
    image_path = r"C:\github\cobalt-multi-agent\samples\NVDA_1H.png"
    if not os.path.exists(image_path):
        print(f"Error: {image_path} not found.")
        return

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    
    state = {
        "messages": [
            HumanMessage(content=[
                {"type": "text", "text": "Analyze this chart using SMC principles and the 7-panel layout."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            ])
        ],
        "verbosity": 1
    }
    
    config = {"configurable": {"thread_id": "test-vision-smc"}}
    
    print("Starting Vision Specialist Node (NVDA_1H)...")
    result = await vision_specialist_node(state, config)
    
    last_msg = result["messages"][-1]
    print("\n--- VISION ANALYSIS RESULT ---\n")
    print(last_msg.content)

if __name__ == "__main__":
    asyncio.run(run_vision_test())
