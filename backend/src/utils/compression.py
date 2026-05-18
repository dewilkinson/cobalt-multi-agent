# Cobalt Multiagent - High-fidelity financial analysis platform
import logging
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

async def condense_artifact(text: str) -> str:
    """
    Compresses a financial artifact (like an analysis report or news article) using the Basic LLM tier.
    Retains critical metrics and directives while discarding conversational fluff.
    """
    if not text or len(text) < 200:
        return text  # Already short enough, skip condensation

    try:
        from src.llms.llm import get_llm_by_type
        llm = get_llm_by_type("basic")
        
        sys_msg = SystemMessage(content=(
            "You are a highly efficient financial data condenser. Your job is to compress the provided artifact into a dense, token-efficient format intended for historical analysis and machine consumption only. "
            "Strip out all conversational fluff, verbose explanations, and excessive formatting. "
            "You MUST preserve ALL occurrences of the following critical metrics and directives if they exist in the text: "
            "Vol, RVOL, CVD, 9/13/50/200 EMA, POC, VAH, VAL, Sortino Daily/Intraday, RSI, Support/Resistance levels, and 'WAIT', 'SCOUT', or 'STRIKE' directives. "
            "Compress the text as much as possible without losing any of this key information."
        ))
        
        user_msg = HumanMessage(content=f"Artifact to condense:\n\n{text}")
        
        response = await llm.ainvoke([sys_msg, user_msg])
        
        if response and response.content:
            if isinstance(response.content, str):
                return response.content
            elif isinstance(response.content, list) and len(response.content) > 0:
                # Extract text from LangChain message chunk list
                return response.content[0].get('text', str(response.content))
            return str(response.content)
            
    except Exception as e:
        logger.error(f"Failed to condense artifact: {e}")
        
    # Fallback to original text if compression fails
    return text
