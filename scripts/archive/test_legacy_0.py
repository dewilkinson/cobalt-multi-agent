import sys
sys.path.append('backend')
import asyncio
import logging
from src.llms.llm import get_llm_by_type
from langchain_core.messages import HumanMessage

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    llm = get_llm_by_type("legacy")
    logger.info("Testing legacy LLM directly to see if we hit a hard 429...")
    try:
        res = await llm.ainvoke([HumanMessage(content="Say hello")])
        logger.info(f"Success! {res.content}")
    except Exception as e:
        logger.error(f"Failed! Exception: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
