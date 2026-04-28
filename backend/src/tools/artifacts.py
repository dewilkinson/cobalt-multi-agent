import os
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = os.path.join(os.getcwd(), "data", "artifacts")


@tool
async def read_session_artifact(symbol: str) -> str:
    """
    Read the cached session artifact (JSON or Markdown) for a specific symbol.
    Use this tool to reuse context instead of refetching remote data.
    """
    symbol = symbol.upper().strip()

    # Check JSON first
    json_path = os.path.join(ARTIFACTS_DIR, f"{symbol}.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            logger.info(f"VLI_ARTIFACT: Injecting cached JSON context for {symbol}")
            return f.read()

    # Check MD
    md_path = os.path.join(ARTIFACTS_DIR, f"{symbol}.md")
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            logger.info(f"VLI_ARTIFACT: Injecting cached Markdown context for {symbol}")
            return f.read()

    # Check Reports Directory
    reports_dir = os.path.join(os.getcwd(), "data", "reports")
    report_path = os.path.join(reports_dir, f"analyze_{symbol.lower()}.md")
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            logger.info(f"VLI_ARTIFACT: Injecting cached Report for {symbol}")
            return f.read()

    return f"[ERROR] No artifact found for {symbol}."
