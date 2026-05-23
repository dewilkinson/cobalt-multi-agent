# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Agent: Journaler - Personal journaling and state tracking tools.

import glob
import logging
import os
from datetime import datetime

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from src.config.configuration import Configuration

from .shared_storage import JOURNALER_CONTEXT

logger = logging.getLogger(__name__)

# Agent-specific resource context (Shared by Journaler sub-modules)
_NODE_RESOURCE_CONTEXT = JOURNALER_CONTEXT


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
    Writes a Daily Trading Report to the Obsidian vault.

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

    base_filename = f"Daily_Trading_Report_{date_str}"
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
def sync_watchlist_to_journal(watchlist_name: str = "Daily Picks", config: RunnableConfig = None):
    """
    Fixed-function tool to sync a watchlist to the 'Targeted Candidates' section of today's journal.
    If the journal doesn't exist, it creates a blank one first.
    """
    vault_path, journal_dir = _get_obsidian_config(config)
    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."

    from .portfolio import get_watchlist_tickers

    tickers = get_watchlist_tickers.func(name=watchlist_name, config=config)

    date_str = datetime.now().strftime("%Y-%m-%d")
    full_journal_dir = os.path.join(vault_path, journal_dir)
    filename = f"Daily_Trading_Report_{date_str}.md"
    file_path = os.path.join(full_journal_dir, filename)

    # Baseline Template
    template = f"# Daily Trading Report - {date_str}\n\n"
    template += "###  Targeted Candidates\n\n"
    template += "###  Morning Session Notes\n- \n\n"
    template += "###  Risk Multipliers (VIX/Gamma)\n- \n\n"

    os.makedirs(full_journal_dir, exist_ok=True)

    content = ""
    if os.path.exists(file_path):
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    else:
        content = template

    # Fixed-Function Section Replacement (Regex-free for reliability)
    header = "###  Targeted Candidates"
    new_list_str = "\n".join([f"- [ ] **{t}**" for t in tickers]) + "\n\n"

    if header in content:
        parts = content.split(header)
        # Find next header or end of file
        rest = parts[1].lstrip()
        if "###" in rest:
            sub_parts = rest.split("###", 1)
            final_content = parts[0] + header + "\n" + new_list_str + "###" + sub_parts[1]
        else:
            final_content = parts[0] + header + "\n" + new_list_str
    else:
        # Header missing - Append to end
        final_content = content + "\n\n" + header + "\n" + new_list_str

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(final_content)
        return f"Watchlist [{watchlist_name}] synced to {filename} section [{header}]."
    except Exception as e:
        return f"[ERROR]: Failed to sync journal: {e}"


@tool
def list_journal_entries(config: RunnableConfig):
    """
    Lists all available Daily Trading Reports in the Obsidian vault.
    Use this to see which dates have existing reports.
    """
    vault_path, journal_dir = _get_obsidian_config(config)

    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."

    full_journal_dir = os.path.join(vault_path, journal_dir)
    if not os.path.exists(full_journal_dir):
        return "No journal entries found (directory does not exist)."

    files = glob.glob(os.path.join(full_journal_dir, "Daily_Trading_Report_*.md"))
    if not files:
        return "No journal entries found."

    entry_names = [os.path.basename(f) for f in files]
    entry_names.sort(reverse=True)
    return entry_names


@tool
def read_journal_entry(filename: str, config: RunnableConfig):
    """
    Reads the content of a specific Daily Trading Report from Obsidian.

    Args:
        filename: The name of the file (e.g., 'Daily_Trading_Report_2026-03-20.md').
    """
    vault_path, journal_dir = _get_obsidian_config(config)

    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."

    file_path = os.path.join(vault_path, journal_dir, filename)

    if not os.path.exists(file_path):
        return f"[ERROR]: Journal file {filename} not found."

    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read journal: {e}")
        return f"[ERROR]: Failed to read journal: {e}"


@tool
def log_feedback(previous_command: str, note: str, config: RunnableConfig = None):
    """
    Appends execution feedback/bugs to a centralized Feedback.md file in the Obsidian vault.
    This is triggered when the user starts a request with "Note:".

    Args:
        previous_command: The exact string instruction the user previously typed.
        note: The feedback provided by the user (minus the "Note:" prefix).
    """
    vault_path, _ = _get_obsidian_config(config)

    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."

    file_path = os.path.join(vault_path, "Feedback.md")
    
    # Define table structure
    header = "| Previous Command | Note |\n| :--- | :--- |\n"
    
    # Escape pipes to avoid breaking MD table syntax
    safe_command = previous_command.replace("|", "\\|")
    safe_note = note.replace("|", "\\|")
    new_row = f"| {safe_command} | {safe_note} |"

    try:
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(header + new_row + "\n")
            return f"Created Feedback.md and logged entry: {new_row}"
        else:
            # Append to existing table
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(new_row + "\n")
            return f"Successfully logged feedback to Feedback.md: {new_row}"
    except Exception as e:
        logger.error(f"Failed to log feedback: {e}")
        return f"[ERROR]: Failed to log feedback: {e}"
