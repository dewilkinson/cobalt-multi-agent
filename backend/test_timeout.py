from dotenv import load_dotenv
load_dotenv()
import asyncio
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from src.graph.builder import build_graph
from langchain_core.messages import HumanMessage

async def main():
    app = build_graph()
    state = {
        "messages": [HumanMessage(content="How do you expect the market to perform next week")],
        "locale": "en-US",
        "research_topic": "market",
        "final_report": "",
        "raw_data_mode": False
    }
    
    print("Running graph...")
    try:
        async for output in app.astream(state, {"recursion_limit": 50}):
            print(list(output.keys()))
            if "reporter" in output:
                # Add type printing to debug
                print("REPORTER TYPE:", type(output["reporter"]))
                if isinstance(output["reporter"], dict):
                    print("REPORTER RESPONSE:", output["reporter"].get("final_report"))
                else:
                    print("REPORTER IS NOT A DICT! It is:", repr(output["reporter"]))
    except Exception as e:
        print("Graph failed:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
