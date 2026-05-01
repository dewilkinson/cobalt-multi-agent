import os
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

REPORTS_DIR = os.path.join(os.getcwd(), 'data', 'reports')
HISTORY_DIR = os.path.join(REPORTS_DIR, 'history')
PERFORMANCE_DIR = os.path.join(REPORTS_DIR, 'performance')

# Ensure directories exist
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(PERFORMANCE_DIR, exist_ok=True)

async def _condense_content(prompt_text: str) -> str:
    """Uses a fast LLM to condense context."""
    try:
        from src.llms.llm import get_llm_by_type
        from langchain_core.messages import HumanMessage, SystemMessage
        
        # Use the fast, cheaper model for summarization tasks
        llm = get_llm_by_type("fast")
        
        messages = [
            SystemMessage(content="You are a data synthesis engine. Condense the following report into a dense, highly factual summary. Maintain all key metrics, patterns, and critical takeaways. Output raw markdown without conversational filler."),
            HumanMessage(content=prompt_text)
        ]
        
        response = await llm.ainvoke(messages)
        return str(getattr(response, "content", response))
    except Exception as e:
        logger.error(f"Failed to condense content: {e}")
        return ""

def update_symbol_rolling_summary(ticker: str, new_report_content: str):
    """
    Called at 5 PM. Condenses the most recent Symbol Analysis Report into the rolling summary.
    """
    summary_path = os.path.join(HISTORY_DIR, f"Historical_Summary_{ticker.upper()}.md")
    
    existing_summary = ""
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            existing_summary = f.read()

    # If it's too big, we condense it. For now, we ask the LLM to integrate the new report.
    prompt = f"""
Existing Historical Summary for {ticker}:
{existing_summary if existing_summary else "No previous history."}

New Analysis Report Generated Today:
{new_report_content}

Integrate the new analysis into the existing historical summary. Create a cohesive, rolling context of the symbol's performance, setups, and key levels. Remove obsolete data but retain pattern recognition over time.
    """
    
    # We spawn it in the background if called synchronously, or just run it via asyncio.run if in thread
    async def _run():
        condensed = await _condense_content(prompt)
        if condensed:
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(condensed)
            logger.info(f"Updated Historical Symbol Summary for {ticker}")
            
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())


def update_performance_rolling_summary(new_report_content: str):
    """
    Condenses the daily post-mortem into a rolling trader performance history.
    """
    summary_path = os.path.join(PERFORMANCE_DIR, "Trader_Performance_History.md")
    
    existing_summary = ""
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            existing_summary = f.read()

    prompt = f"""
Existing Trader Performance History:
{existing_summary if existing_summary else "No previous history."}

Today's Post-Mortem Report:
{new_report_content}

Integrate today's performance into the rolling performance history. Focus on recurring mistakes, emotional patterns, strategy adherence, and ongoing strengths/weaknesses. Keep it dense and actionable for future reference.
    """
    
    async def _run():
        condensed = await _condense_content(prompt)
        if condensed:
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(condensed)
            logger.info("Updated Trader Performance History")
            
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())


def get_historical_symbol_summary(ticker: str) -> str:
    """Returns the rolling historical summary for a symbol to be injected into state."""
    summary_path = os.path.join(HISTORY_DIR, f"Historical_Summary_{ticker.upper()}.md")
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def get_trader_performance_summary() -> str:
    """Returns the rolling trader performance summary to be injected into post-mortems."""
    summary_path = os.path.join(PERFORMANCE_DIR, "Trader_Performance_History.md")
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def write_obsidian_daily_report(content: str):
    """Writes the raw Daily Trading Report to the Obsidian Journal vault."""
    try:
        from src.tools.journal import _get_obsidian_config
        vault_path, journal_dir = _get_obsidian_config(None)
        
        if not vault_path:
            logger.error("Obsidian vault path not configured for Daily Trading Report")
            return
            
        full_journal_dir = os.path.join(vault_path, journal_dir)
        os.makedirs(full_journal_dir, exist_ok=True)
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(full_journal_dir, f"Daily_Trading_Report_{date_str}.md")
        
        # We replace the file if it exists, since it's the 5 PM raw post mortem
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Wrote raw Daily Trading Report to Obsidian: {file_path}")
    except Exception as e:
        logger.error(f"Failed to write Obsidian report: {e}")
