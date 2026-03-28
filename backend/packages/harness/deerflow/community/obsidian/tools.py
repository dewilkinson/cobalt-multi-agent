import os
import re
import logging
from pathlib import Path
from typing import List, Optional

from langchain.tools import tool

from deerflow.config import get_app_config

logger = logging.getLogger(__name__)

# Standard mount point for Obsidian inside the DeerFlow sandbox (if running inside)
# However, these tools run in the backend (host), so they need the host path.
def _get_obsidian_vault_path() -> Path:
    config = get_app_config().get_tool_config("read_obsidian_note")
    if config is not None and "vault_path" in config.model_extra:
        return Path(config.model_extra.get("vault_path"))
    
    # Fallback to environment variable or standard mount point
    env_path = os.getenv("OBSIDIAN_VAULT_PATH")
    if env_path:
        return Path(env_path)
    
    return Path("/mnt/obsidian")

def _resolve_obsidian_path(path: str) -> Path:
    """Resolve an Obsidian path relative to the vault path, ensuring it stays within the vault."""
    vault_path = _get_obsidian_vault_path()
    
    # Ensure path is relative and doesn't use .. to escape
    clean_path = path.lstrip("/")
    if ".." in clean_path:
        raise ValueError("Access denied: path traversal attempt detected.")
    
    # Pre-pend the vault path
    full_path = (vault_path / clean_path).resolve()
    
    # Ensure it's inside the vault path
    if not str(full_path).startswith(str(vault_path.resolve())):
        raise ValueError("Access denied: path is outside the Obsidian vault.")
        
    return full_path

def _ensure_md_extension(path: str) -> str:
    """Ensure the path ends with .md if it doesn't already."""
    if not path.lower().endswith(".md"):
        return f"{path}.md"
    return path

@tool("read_obsidian_note", parse_docstring=True)
def read_obsidian_note(path: str) -> str:
    """Read the content of an Obsidian note.
    
    Args:
        path: Relative path to the note (e.g., 'Work/Project.md' or 'Inbox/Ideas').
    """
    try:
        full_path = _resolve_obsidian_path(_ensure_md_extension(path))
        if not full_path.exists():
            return f"Error: Note not found at {path}"
        
        return full_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading note: {str(e)}"

@tool("write_obsidian_note", parse_docstring=True)
def write_obsidian_note(path: str, content: str) -> str:
    """Create or overwrite an Obsidian note.
    
    Args:
        path: Relative path to the note (e.g., 'Drafts/NewNote.md').
        content: The content to write.
    """
    try:
        full_path = _resolve_obsidian_path(_ensure_md_extension(path))
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        full_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing note: {str(e)}"

@tool("append_obsidian_note", parse_docstring=True)
def append_obsidian_note(path: str, content: str) -> str:
    """Append content to an existing Obsidian note.
    
    Args:
        path: Relative path to the note.
        content: The content to append.
    """
    try:
        full_path = _resolve_obsidian_path(_ensure_md_extension(path))
        if not full_path.exists():
            return f"Error: Note not found at {path}. Use write_obsidian_note instead."
        
        with open(full_path, "a", encoding="utf-8") as f:
            f.write(f"\n{content}")
        return f"Successfully appended to {path}"
    except Exception as e:
        return f"Error appending to note: {str(e)}"

@tool("list_obsidian_notes", parse_docstring=True)
def list_obsidian_notes(path: str = "") -> str:
    """List notes in an Obsidian vault directory.
    
    Args:
        path: Optional relative path to a folder (e.g., 'Meetings'). 
              Leave empty to list the vault root.
    """
    try:
        full_path = _resolve_obsidian_path(path)
        if not full_path.exists():
            return f"Error: Directory not found at {path}"
        if not full_path.is_dir():
            return f"Error: {path} is not a directory"

        notes = []
        for item in full_path.iterdir():
            icon = "📁" if item.is_dir() else "📄"
            notes.append(f"{icon} {item.name}")
        
        if not notes:
            return "No notes or folders found."
        
        return "\n".join(sorted(notes))
    except Exception as e:
        return f"Error listing notes: {str(e)}"

@tool("search_obsidian_notes", parse_docstring=True)
def search_obsidian_notes(query: str) -> str:
    """Search for a keyword across all notes in the Obsidian vault.
    
    Args:
        query: The string to search for.
    """
    try:
        vault_path = _get_obsidian_vault_path()
        matches = []
        
        # Simple recursive search for .md files
        for note_path in vault_path.rglob("*.md"):
            try:
                content = note_path.read_text(encoding="utf-8")
                if query.lower() in content.lower():
                    # Find matching lines
                    lines = content.splitlines()
                    for i, line in enumerate(lines):
                        if query.lower() in line.lower():
                            rel_path = note_path.relative_to(vault_path)
                            matches.append(f"{rel_path.as_posix()}:{i+1}: {line.strip()}")
                            if len(matches) >= 50: # Cap results for context safety
                                break
                if len(matches) >= 50:
                    break
            except Exception:
                continue # Skip files that can't be read

        if not matches:
            return f"No matches found for '{query}'."
        
        return "\n".join(matches[:50])
    except Exception as e:
        return f"Error searching notes: {str(e)}"
