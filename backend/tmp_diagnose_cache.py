
import asyncio
import logging
from langchain_core.messages import HumanMessage
from src.llms.llm import get_llm_by_type
from src.config.agents import AGENT_LLM_MAP
from src.tools import get_stock_quote, invalidate_market_cache

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def diagnose():
    # 1. Setup LLM and tools
    llm_type = AGENT_LLM_MAP.get("parser", "basic")
    llm = get_llm_by_type(llm_type)
    tools = [get_stock_quote, invalidate_market_cache]
    llm_with_tools = llm.bind_tools(tools)
    
    # 2. Test Message
    messages = [HumanMessage(content="get fresh VIX")]
    
    print("\n--- DIAGNOSING PARSER FAST-PATH ---")
    response = await llm_with_tools.ainvoke(messages)
    
    print(f"Tool calls generated: {response.tool_calls}")
    
    for tool_call in response.tool_calls:
        print(f"Tool: {tool_call['name']}")
        print(f"Args: {tool_call['args']}")

if __name__ == "__main__":
    asyncio.run(diagnose())
