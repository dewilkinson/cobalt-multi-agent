import asyncio
import base64
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from src.tools.screenshot import _snapper_worker
from src.llms.llm import get_llm_by_type
from langchain_core.messages import HumanMessage

async def diagnostic_test():
    print("🚀 Starting AI Studio Diagnostic Test...")
    
    # 1. Take snapshot
    print("📸 Taking snapshot of primary monitor...")
    snapshot_json_str = await asyncio.to_thread(_snapper_worker, "desktop")
    snapshot_data = json.loads(snapshot_json_str)
    
    if "error" in snapshot_data:
        print(f"❌ Error taking snapshot: {snapshot_data['error']}")
        return
    
    b64_image = snapshot_data["images"][0]
    
    # Save the snapshot to disk for inspection
    print("💾 Saving snapshot to 'studio_diagnostic_capture.png'...")
    image_data = base64.b64decode(b64_image.split(",")[1])
    with open("studio_diagnostic_capture.png", "wb") as f:
        f.write(image_data)
    print(f"✅ Snapshot saved to {os.path.abspath('studio_diagnostic_capture.png')}")

    # 2. Vision Extraction
    print("🧠 Invoking Gemini Vision for extraction...")
    vision_llm = get_llm_by_type("vision")
    
    prompt = (
        "Look at this screenshot of the Google AI Studio activity page. "
        "Extract the 'Monthly credits' and 'Additional credits' remaining. "
        "Return them as a JSON object: {'monthly': value, 'additional': value, 'total': value}. "
        "The values should be numbers (if '25.0', return 25.0). "
        "Return ONLY the JSON. If nothing is found, return {'monthly': 'Unknown', 'additional': 'Unknown', 'total': 'Unknown'}."
    )
    
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": b64_image}}
        ]
    )
    
    try:
        response = await vision_llm.ainvoke([message])
        content = response.content.strip()
        print(f"🤖 LLM Response:\n{content}")
        
        # Try parsing
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        try:
            parsed = json.loads(content)
            print("✅ Parsed JSON successfully:")
            print(json.dumps(parsed, indent=2))
        except:
            print("⚠️ Failed to parse LLM response as JSON.")
            
    except Exception as e:
        print(f"❌ LLM error: {e}")

if __name__ == "__main__":
    asyncio.run(diagnostic_test())
