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
    print("Running _invoke_vli_agent for HPE...")
    try:
        response_text, final_state = await _invoke_vli_agent(
            text="analyze HPE",
            reporter_llm_type="reasoning",
            vli_llm_type="reasoning",
            thread_id="test_hpe",
            thinking_mode=False
        )
        print("\n=== FINAL REPORT RESPONSE ===\n")
        print(response_text)
        print("\n=== END REPORT ===\n")
        
        # Save response
        with open("hpe_report_test_out.md", "w", encoding="utf-8") as f:
            f.write(response_text)
            
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
