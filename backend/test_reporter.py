import asyncio
from dotenv import load_dotenv
load_dotenv()
from src.graph.nodes.common_vli import _run_node_with_tiered_fallback
from langchain_core.messages import HumanMessage, SystemMessage
from src.prompts.template import apply_prompt_template

async def main():
    state = {
        "messages": [HumanMessage(content="MSFT is doing great. Buy now.")],
        "research_topic": "MSFT",
        "locale": "en-US",
        "final_report": "",
        "raw_data_mode": False
    }
    
    messages = apply_prompt_template("reporter", state, configurable=None)
    
    try:
        response, fb = await _run_node_with_tiered_fallback("reporter", state, config={}, messages=messages)
        print("Success:", type(response.content))
        print(str(response.content)[:200])
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    asyncio.run(main())
