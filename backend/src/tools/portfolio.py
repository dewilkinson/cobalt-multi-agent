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

# Agent: Portfolio Manager - Watchlist and Ledger management tools.

import glob
import logging
import os
from typing import Any

import yaml
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from src.config.configuration import Configuration

logger = logging.getLogger(__name__)


def _get_obsidian_config(config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    settings = configurable.obsidian_settings if configurable.obsidian_settings else {}
    vault_path = settings.get("OBSIDIAN_VAULT_PATH") or os.getenv("OBSIDIAN_VAULT_PATH")
    return vault_path


@tool
def update_watchlist(tickers: list[str], name: str = "Tactical", action: str = "add", metadata: dict[str, Any] | None = None, config: RunnableConfig = None):
    """
    Manages a named Watchlist file in the Obsidian vault (_cobalt directory).
    Filename: Watchlist_{name}.md

    Args:
        tickers: List of ticker symbols to modify.
        name: The suffix for the watchlist name (e.g., 'Daily', 'Index', 'Futures', 'Tech').
        action: 'add', 'remove', or 'list'.
        metadata: Optional dictionary of metadata to store as YAML frontmatter (e.g., {'Sector': 'Energy', 'Conviction': 'High'}).
    """
    vault_path = _get_obsidian_config(config)
    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."

    cobalt_dir = os.path.join(vault_path, "_cobalt")
    if not os.path.exists(cobalt_dir):
        os.makedirs(cobalt_dir, exist_ok=True)

    filename = f"Watchlist_{name}.md" if name else "Watchlist.md"
    watchlist_path = os.path.join(cobalt_dir, filename)

    # Read existing
    current_watchlist = []
    current_metadata = {}

    if os.path.exists(watchlist_path):
        with open(watchlist_path, encoding="utf-8") as f:
            content = f.read()
            # Parse YAML if present
            if content.startswith("---"):
                try:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        current_metadata = yaml.safe_load(parts[1]) or {}
                        body = parts[2]
                        current_watchlist = [line.strip().replace("- ", "") for line in body.splitlines() if line.startswith("- ")]
                except Exception as e:
                    logger.warning(f"Failed to parse YAML frontmatter in {filename}: {e}")
                    # Fallback to simple parsing
                    current_watchlist = [line.strip().replace("- ", "") for line in content.splitlines() if line.startswith("- ")]
            else:
                current_watchlist = [line.strip().replace("- ", "") for line in content.splitlines() if line.startswith("- ")]

    if action == "list":
        return f"Watchlist [{name}]: {', '.join([str(t) for t in current_watchlist])}" if current_watchlist else f"Watchlist [{name}] is empty."

    # Normalize tickers
    tickers = [t.upper().strip() for t in tickers]

    if action == "add":
        new_tickers = [t for t in tickers if t not in current_watchlist]
        current_watchlist.extend(new_tickers)
        msg = f"Added: {', '.join([str(t) for t in new_tickers])}" if new_tickers else "No new tickers to add."
    elif action == "remove":
        current_watchlist = [t for t in current_watchlist if t not in tickers]
        msg = f"Removed: {', '.join([str(t) for t in tickers])}"
    elif action == "clear":
        current_watchlist = []
        msg = f"Watchlist [{name}] cleared."
    else:
        return "[ERROR]: Invalid action. Use 'add', 'remove', 'list', or 'clear'."

    # Update metadata if provided
    if metadata:
        current_metadata.update(metadata)

    # Sort and Write back
    current_watchlist.sort()
    try:
        with open(watchlist_path, "w", encoding="utf-8") as f:
            if current_metadata:
                f.write("---\n")
                yaml.dump(current_metadata, f, default_flow_style=False)
                f.write("---\n\n")
            f.write(f"# Cobalt Watchlist: {name}\n\n")
            for ticker in current_watchlist:
                f.write(f"- {ticker}\n")
        return f"{msg} | Watchlist [{name}] updated at {watchlist_path}"
    except Exception as e:
        return f"[ERROR]: Failed to write watchlist {name}: {e}"


@tool
def get_watchlist_tickers(name: str = "Tactical", config: RunnableConfig = None) -> list[str]:
    """
    Returns a clean list of ticker symbols from a named Watchlist.
    Use this as a pre-requisite for batch analysis or risk auditing.
    """
    vault_path = _get_obsidian_config(config)
    if not vault_path:
        return []

    filename = f"Watchlist_{name}.md" if name else "Watchlist.md"
    watchlist_path = os.path.join(vault_path, "_cobalt", filename)

    tickers = []
    if os.path.exists(watchlist_path):
        with open(watchlist_path, encoding="utf-8") as f:
            content = f.read()
            # Skip YAML frontmatter if present
            if content.startswith("---"):
                parts = content.split("---", 2)
                body = parts[2] if len(parts) >= 3 else ""
            else:
                body = content
            tickers = [line.strip().replace("- ", "") for line in body.splitlines() if line.startswith("- ")]
    return tickers


@tool
def swap_watchlist_item(old_ticker: str, new_ticker: str, watchlist_name: str = "Tactical", config: RunnableConfig = None):
    """
    High-conviction tool to swap one ticker for another in a specific named Watchlist.
    """
    old_ticker = old_ticker.upper().strip()
    new_ticker = new_ticker.upper().strip()

    # We use the underlying function to avoid StructuredTool call errors
    res_remove = update_watchlist.func(tickers=[old_ticker], name=watchlist_name, action="remove", config=config)
    if "[ERROR]" in res_remove:
        return res_remove

    res_add = update_watchlist.func(tickers=[new_ticker], name=watchlist_name, action="add", config=config)
    if "[ERROR]" in res_add:
        return res_add

    return f"Successfully swapped {old_ticker} for {new_ticker} in the Cobalt Watchlist [{watchlist_name}]."


@tool
def get_portfolio_balance_report(config: RunnableConfig = None):
    """
    Aggregates all named Watchlists (Watchlist_*.md) and the Portfolio Ledger.
    """
    vault_path = _get_obsidian_config(config)
    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."

    cobalt_dir = os.path.join(vault_path, "_cobalt")
    reports = []

    # Ledger
    ledger_path = os.path.join(cobalt_dir, "Portfolio_Ledger.md")
    if os.path.exists(ledger_path):
        with open(ledger_path, encoding="utf-8") as f:
            reports.append(f"--- Portfolio_Ledger.md ---\n{f.read()}")

    # Watchlists
    list_files = glob.glob(os.path.join(cobalt_dir, "Watchlist_*.md"))
    # Also include the generic one if it exists
    if os.path.exists(os.path.join(cobalt_dir, "Watchlist.md")):
        list_files.append(os.path.join(cobalt_dir, "Watchlist.md"))

    for path in sorted(list_files):
        filename = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            reports.append(f"--- {filename} ---\n{f.read()}")

    if not reports:
        return "No portfolio data or watchlists found in the vault."

    return "\n\n".join([str(r) for r in reports])


@tool
def update_portfolio_ledger(position_data: str, config: RunnableConfig = None):
    """
    Updates the 'Portfolio_Ledger.md' in the Obsidian vault (_cobalt directory).
    """
    vault_path = _get_obsidian_config(config)
    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."

    cobalt_dir = os.path.join(vault_path, "_cobalt")
    if not os.path.exists(cobalt_dir):
        os.makedirs(cobalt_dir, exist_ok=True)

    ledger_path = os.path.join(cobalt_dir, "Portfolio_Ledger.md")

    try:
        with open(ledger_path, "w", encoding="utf-8") as f:
            f.write(f"# Portfolio Ledger\n\n{position_data}")
        return f"Portfolio ledger successfully updated at {ledger_path}"
    except Exception as e:
        return f"[ERROR]: Failed to update ledger: {e}"


@tool
def export_scanner_watchlists(config: RunnableConfig = None) -> str:
    """
    Exports the scanner results (STRIKE_LIST.json) categorized by tier to TradingView watchlist files.
    Watchlist files are stored in backend/data/exports/ as watchlist_*.txt.
    """
    try:
        import sys
        proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if proj_root not in sys.path:
            sys.path.append(proj_root)
            
        from scripts.utils.export_tradingview_watchlists import main as run_export
        
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            run_export()
        output = f.getvalue()
        
        return f"[SUCCESS]: Watchlists exported successfully.\n{output}"
    except Exception as e:
        logger.error(f"Failed to export scanner watchlists: {e}")
        return f"[ERROR]: Failed to export scanner watchlists: {e}"
