import asyncio
import time
from src.llms.llm import get_llm_by_type
from src.config.agents import AGENT_LLM_MAP
from src.prompts.planner_model import Plan
from src.tools.shared_storage import GLOBAL_CONTEXT
from langchain_core.messages import HumanMessage

async def main():
    print("Testing coordinator LLM call...")
    llm = get_llm_by_type(AGENT_LLM_MAP.get("coordinator", "reasoning"))
    structured_llm = llm.with_structured_output(Plan)
    
    start = time.time()
    try:
        messages = [HumanMessage(content="get sortino of VIX")]
        res = await asyncio.wait_for(structured_llm.ainvoke(messages), timeout=45.0)
        print(f"Success in {time.time() - start:.2f}s: {res}")
    except asyncio.TimeoutError:
        print(f"Timeout after {time.time() - start:.2f}s")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
