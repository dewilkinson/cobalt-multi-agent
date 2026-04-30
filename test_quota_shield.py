import sys
sys.path.append('backend')
import asyncio
import logging
from src.llms.llm import get_llm_by_type
from langchain_core.messages import HumanMessage

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_llm(i):
    llm = get_llm_by_type("legacy")
    logger.info(f"Task {i}: Starting")
    try:
        # A simple prompt that generates a few tokens
        res = await llm.ainvoke([HumanMessage(content=f"Say hello {i}")])
        logger.info(f"Task {i}: Completed! Result: {res.content.strip()[:20]}")
        return True
    except Exception as e:
        logger.error(f"Task {i}: FAILED! {e}")
        return False

async def main():
    logger.info("Spawning 20 parallel LLM requests to force a 429 RPM limit...")
    tasks = [test_llm(i) for i in range(20)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = sum(1 for r in results if r is True)
    logger.info(f"\n--- TEST RESULTS ---")
    logger.info(f"Successful Tasks: {success_count} / 20")
    if success_count == 20:
        logger.info("SUCCESS: Quota shield perfectly absorbed the rate limit spike!")
    else:
        logger.info("FAILURE: Some tasks failed or crashed.")

if __name__ == "__main__":
    asyncio.run(main())
