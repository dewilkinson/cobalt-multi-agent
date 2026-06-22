import asyncio
import os
import sys

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

# Force logging to console
import logging
logging.basicConfig(level=logging.INFO)

from src.server.app import _invoke_vli_agent

async def main():
    print("Running _invoke_vli_agent to generate VNO analysis report...")
    try:
        response_text, final_state = await _invoke_vli_agent(
            text="analyze VNO",
            reporter_llm_type="reasoning",
            vli_llm_type="reasoning",
            thread_id="generate_vno",
            thinking_mode=False
        )
        print("\n=== FINAL REPORT RESPONSE ===\n")
        print(response_text)
        print("\n=== END REPORT ===\n")
        
        # Save to data/reports/analyze_vno.md
        p1 = "data/reports/analyze_vno.md"
        os.makedirs(os.path.dirname(p1), exist_ok=True)
        with open(p1, "w", encoding="utf-8") as f:
            f.write(response_text)
        print(f"Saved to {p1}")

        # Save to backend/data/reports/analyze_vno.md
        p2 = "backend/data/reports/analyze_vno.md"
        os.makedirs(os.path.dirname(p2), exist_ok=True)
        with open(p2, "w", encoding="utf-8") as f:
            f.write(response_text)
        print(f"Saved to {p2}")
            
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
