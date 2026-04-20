import asyncio
import sys
sys.path.append(r'c:\github\cobalt-multi-agent\backend')
from langchain_core.messages import HumanMessage
from src.graph.nodes.reporter import reporter_node

async def run_test():
    state = {
        "messages": [HumanMessage(content="test")],
        "intent": "SENTIMENT_REPORT",
    }
    config = {}
    
    try:
        res = await reporter_node(state, config)
        print("RESULT:")
        print(res.get("final_report", ""))
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_test())
