import os
import glob
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
import logging
from datetime import datetime
from src.config.configuration import Configuration

logger = logging.getLogger(__name__)

def _get_obsidian_config(config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    settings = configurable.obsidian_settings if configurable.obsidian_settings else {}
    
    vault_path = settings.get("OBSIDIAN_VAULT_PATH") or os.getenv("OBSIDIAN_VAULT_PATH")
    journal_dir = settings.get("OBSIDIAN_JOURNAL_DIR") or os.getenv("OBSIDIAN_JOURNAL_DIR", "Journals")
    
    return vault_path, journal_dir

@tool
def get_journal_folder(config: RunnableConfig):
    """
    Returns the current absolute path of the journal folder being used.
    """
    vault_path, journal_dir = _get_obsidian_config(config)
    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."
    return os.path.abspath(os.path.join(vault_path, journal_dir))

@tool
def set_journal_folder(new_journal_dir: str, config: RunnableConfig):
    """
    Changes the sub-directory where journals are stored within the vault.
    
    Args:
        new_journal_dir: The new sub-directory path (e.g., 'trading/journal').
    """
    vault_path, _ = _get_obsidian_config(config)
    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."
        
    full_path = os.path.join(vault_path, new_journal_dir)
    # We don't check if it exists here; we'll create it on the first write if needed.
    # But for verification, we'll return the full path.
    return f"Successfully changed journal folder to: {os.path.abspath(full_path)}. (Note: This change persists for the current session. Update your client .env for permanent changes.)"

@tool
def write_daily_journal(content: str, date_str: str = None, config: RunnableConfig = None):
    """
    Writes a daily trading journal entry to the Obsidian vault.
    
    Args:
        content: The full markdown content of the journal entry.
        date_str: Optional date in YYYY-MM-DD format. Defaults to today.
    """
    vault_path, journal_dir = _get_obsidian_config(config)
    
    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."
    
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    full_journal_dir = os.path.join(vault_path, journal_dir)
    if not os.path.exists(full_journal_dir):
        os.makedirs(full_journal_dir, exist_ok=True)
        
    base_filename = f"Trading_Journal_{date_str}"
    file_path = os.path.join(full_journal_dir, f"{base_filename}.md")
    
    # Handle conflicts with numerical suffix
    counter = 1
    while os.path.exists(file_path):
        file_path = os.path.join(full_journal_dir, f"{base_filename} ({counter}).md")
        counter += 1
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Journal entry written to {file_path}")
        return f"Successfully written journal to: {file_path}"
    except Exception as e:
        logger.error(f"Failed to write journal: {e}")
        return f"[ERROR]: Failed to write journal: {e}"

@tool
def list_journal_entries(config: RunnableConfig):
    """
    Lists all available trading journal entries in the Obsidian vault.
    Use this to see which dates have existing journals.
    """
    vault_path, journal_dir = _get_obsidian_config(config)
    
    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."
        
    full_journal_dir = os.path.join(vault_path, journal_dir)
    if not os.path.exists(full_journal_dir):
        return "No journal entries found (directory does not exist)."
        
    files = glob.glob(os.path.join(full_journal_dir, "Trading_Journal_*.md"))
    if not files:
        return "No journal entries found."
        
    entry_names = [os.path.basename(f) for f in files]
    entry_names.sort(reverse=True)
    return entry_names

@tool
def read_journal_entry(filename: str, config: RunnableConfig):
    """
    Reads the content of a specific trading journal entry from Obsidian.
    
    Args:
        filename: The name of the file (e.g., 'Trading_Journal_2026-03-20.md').
    """
    vault_path, journal_dir = _get_obsidian_config(config)
    
    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."
        
    file_path = os.path.join(vault_path, journal_dir, filename)
    
    if not os.path.exists(file_path):
        return f"[ERROR]: Journal file {filename} not found."
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read journal: {e}")
        return f"[ERROR]: Failed to read journal: {e}"
