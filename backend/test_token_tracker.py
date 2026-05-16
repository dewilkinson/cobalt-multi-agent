import asyncio
from src.llms.llm import get_llm_by_type
from src.utils.token_tracker import token_tracker

async def main():
    print(f"Initial tally: {token_tracker.get_tally()}")
    
    llm = get_llm_by_type("basic")
    print(f"LLM loaded. Callbacks: {llm.callbacks}")
    
    if hasattr(llm, 'llm'):
        print(f"Base LLM Callbacks: {llm.llm.callbacks}")
        
    print("Invoking LLM...")
    try:
        response = await llm.ainvoke("Say hello!")
        print(f"Response: {response.content}")
        print(f"Usage Metadata: {getattr(response, 'response_metadata', {})}")
        print(f"Token Usage (usage_metadata attribute): {getattr(response, 'usage_metadata', {})}")
    except Exception as e:
        print(f"LLM invoke failed: {e}")
        
    print(f"Final tally: {token_tracker.get_tally()}")

if __name__ == "__main__":
    asyncio.run(main())
