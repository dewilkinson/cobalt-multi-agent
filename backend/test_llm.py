import asyncio
from src.llms.llm import get_llm_by_type
async def main():
    try:
        print("Loading...")
        llm = get_llm_by_type("reasoning")
        print(f"Model ID: {getattr(llm, 'model', 'unknown')}")
        res = await llm.ainvoke("Say hello")
        print("Success:", res.content)
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
