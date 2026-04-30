import asyncio
from src.llms.llm import get_llm_by_type
from langchain_core.messages import SystemMessage, HumanMessage

async def main():
    try:
        print("Loading LLM...")
        llm = get_llm_by_type("reasoning")
        msgs = [
            SystemMessage(content="You are a reporter"),
            HumanMessage(content="Analyze this: AAPL")
        ]
        res = await llm.ainvoke(msgs)
        print("Success:", res.content)
    except Exception as e:
        print("Error encountered!!!", type(e).__name__, str(e))

asyncio.run(main())
