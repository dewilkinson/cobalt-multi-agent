"""Memory storage providers."""

import abc
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from deerflow.config.agents_config import AGENT_NAME_PATTERN
from deerflow.config.memory_config import get_memory_config
from deerflow.config.paths import get_paths

logger = logging.getLogger(__name__)


def create_empty_memory() -> dict[str, Any]:
    """Create an empty memory structure."""
    return {
        "version": "1.0",
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
        "user": {
            "workContext": {"summary": "", "updatedAt": ""},
            "personalContext": {"summary": "", "updatedAt": ""},
            "topOfMind": {"summary": "", "updatedAt": ""},
        },
        "history": {
            "recentMonths": {"summary": "", "updatedAt": ""},
            "earlierContext": {"summary": "", "updatedAt": ""},
            "longTermBackground": {"summary": "", "updatedAt": ""},
        },
        "facts": [],
    }


class MemoryStorage(abc.ABC):
    """Abstract base class for memory storage providers."""

    @abc.abstractmethod
    def load(self, agent_name: str | None = None) -> dict[str, Any]:
        """Load memory data for the given agent."""
        pass

    @abc.abstractmethod
    def reload(self, agent_name: str | None = None) -> dict[str, Any]:
        """Force reload memory data for the given agent."""
        pass

    @abc.abstractmethod
    def save(self, memory_data: dict[str, Any], agent_name: str | None = None) -> bool:
        """Save memory data."""
        pass

    @abc.abstractmethod
    def backup(self, agent_name: str | None = None) -> str:
        """Create a backup of the memory and return the path."""
        pass

    def _check_registry(self, target_id: str | None) -> None:
        """Enforce explicit registry for shared and global memory.
        
        If target_id is None, it's global memory. If it's a string, it's an agent or shared pool.
        Hard fails if the ID is not in the authorized storage_registry.
        """
        config = get_memory_config()
        # Private storage for known agents is always allowed via policy map check if needed,
        # but shared/global IDs must be in the registry.
        if not config.storage_registry:
            return # Registry disabled (backward compatibility)

        registry_id = target_id or "global"
        if registry_id not in config.storage_registry:
            logger.error("Registry Violation: Storage ID '%s' is not authorized in config.yaml", registry_id)
            raise PermissionError(f"Access Denied: Storage ID '{registry_id}' is not in the explicit registry.")


class FileMemoryStorage(MemoryStorage):
    """File-based memory storage provider with high-fidelity locking."""

    def __init__(self):
        """Initialize the file memory storage."""
        from deerflow.agents.memory.lock import get_lock_provider
        self._lock_provider = get_lock_provider()
        # Per-agent memory cache: keyed by agent_name (None = global)
        # Value: (memory_data, file_mtime)
        self._memory_cache: dict[str | None, tuple[dict[str, Any], float | None]] = {}

    def _validate_agent_name(self, agent_name: str) -> None:
        """Validate agent name safety."""
        if not agent_name:
            raise ValueError("Agent name must be a non-empty string.")
        if not AGENT_NAME_PATTERN.match(agent_name):
            raise ValueError(f"Invalid agent name {agent_name!r}")

    def _get_memory_file_path(self, agent_name: str | None = None) -> Path:
        """Get the path to the memory file."""
        if agent_name is not None:
            self._validate_agent_name(agent_name)
            return get_paths().agent_memory_file(agent_name)

        config = get_memory_config()
        if config.storage_path:
            p = Path(config.storage_path)
            return p if p.is_absolute() else get_paths().base_dir / p
        return get_paths().memory_file

    def _load_memory_from_file(self, agent_name: str | None = None) -> dict[str, Any]:
        """Load memory data from file."""
        file_path = self._get_memory_file_path(agent_name)
        if not file_path.exists():
            return create_empty_memory()

        try:
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load memory file: %s", e)
            return create_empty_memory()

    def load(self, agent_name: str | None = None) -> dict[str, Any]:
        """Load memory data (with Registry and MTime check)."""
        self._check_registry(agent_name)
        file_path = self._get_memory_file_path(agent_name)
        try:
            current_mtime = file_path.stat().st_mtime if file_path.exists() else None
        except OSError:
            current_mtime = None

        cached = self._memory_cache.get(agent_name)
        if cached is None or cached[1] != current_mtime:
            memory_data = self._load_memory_from_file(agent_name)
            self._memory_cache[agent_name] = (memory_data, current_mtime)
            return memory_data
        return cached[0]

    def reload(self, agent_name: str | None = None) -> dict[str, Any]:
        """Reload memory data from file."""
        file_path = self._get_memory_file_path(agent_name)
        memory_data = self._load_memory_from_file(agent_name)
        try:
            mtime = file_path.stat().st_mtime if file_path.exists() else None
        except OSError:
            mtime = None
        self._memory_cache[agent_name] = (memory_data, mtime)
        return memory_data

    def save(self, memory_data: dict[str, Any], agent_name: str | None = None) -> bool:
        """Save memory data to file with Registry and Lock enforcement."""
        self._check_registry(agent_name)
        file_path = self._get_memory_file_path(agent_name)
        lock_id = f"memory_{agent_name or 'global'}"
        
        if not self._lock_provider.acquire(lock_id):
            logger.error("Failed to acquire lock for %s", lock_id)
            return False

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            memory_data["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
            temp_path = file_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(memory_data, f, indent=2, ensure_ascii=False)
            temp_path.replace(file_path)
            
            try:
                mtime = file_path.stat().st_mtime
            except OSError:
                mtime = None
            self._memory_cache[agent_name] = (memory_data, mtime)
            return True
        except OSError as e:
            logger.error("Failed to save memory file: %s", e)
            return False
        finally:
            self._lock_provider.release(lock_id)

    def backup(self, agent_name: str | None = None) -> str:
        """Create a timestamped backup in _memory/backups/ with 10-count retention."""
        self._check_registry(agent_name)
        file_path = self._get_memory_file_path(agent_name)
        if not file_path.exists():
            return "No memory to backup."
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{agent_name or 'global'}_{timestamp}.json"
        backup_path = get_paths().backups_dir / backup_name
        
        try:
            get_paths().backups_dir.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(file_path, backup_path)
            
            # Retention: Delete oldest if > 10
            backups = sorted(get_paths().backups_dir.glob(f"{agent_name or 'global'}_*.json"), key=os.path.getmtime)
            if len(backups) > 10:
                for old in backups[:-10]:
                    old.unlink()
            
            return str(backup_path)
        except Exception as e:
            return f"Backup failed: {str(e)}"


class ObsidianMemoryStorage(MemoryStorage):
    """Obsidain-backed memory storage using Markdown wrappers for GitHub/Telegram compatibility."""

    def __init__(self):
        from deerflow.agents.memory.lock import get_lock_provider
        self._lock_provider = get_lock_provider()
        self._memory_cache: dict[str | None, tuple[dict[str, Any], float | None]] = {}

    def _get_obsidian_path(self, agent_name: str | None = None) -> Path:
        from deerflow.community.obsidian.tools import _resolve_obsidian_path
        root = get_paths().obsidian_memory_dir()
        if agent_name is None:
            return _resolve_obsidian_path(str(root / "global.md"))
        return _resolve_obsidian_path(str(root / "agents" / f"{agent_name}.md"))

    def _extract_json_from_md(self, content: str) -> dict[str, Any]:
        match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return create_empty_memory()

    def _wrap_json_in_md(self, memory_data: dict[str, Any], agent_name: str | None = None) -> str:
        last_updated = datetime.utcnow().isoformat() + "Z"
        scope = agent_name or "global"
        return f"""---
scope: {scope}
lastUpdated: {last_updated}
---
# Agent Memory: {scope.capitalize()}

This file is automatically managed by Cobalt Multi-Agent. 
Manual edits within the JSON block may be overwritten.

```json
{json.dumps(memory_data, indent=2, ensure_ascii=False)}
```
"""

    def load(self, agent_name: str | None = None) -> dict[str, Any]:
        self._check_registry(agent_name)
        file_path = self._get_obsidian_path(agent_name)
        if not file_path.exists():
            return create_empty_memory()
        
        try:
            content = file_path.read_text(encoding="utf-8")
            return self._extract_json_from_md(content)
        except Exception:
            return create_empty_memory()

    def reload(self, agent_name: str | None = None) -> dict[str, Any]:
        return self.load(agent_name)

    def save(self, memory_data: dict[str, Any], agent_name: str | None = None) -> bool:
        self._check_registry(agent_name)
        file_path = self._get_obsidian_path(agent_name)
        lock_id = f"obsidian_memory_{agent_name or 'global'}"
        
        if not self._lock_provider.acquire(lock_id):
            return False

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            content = self._wrap_json_in_md(memory_data, agent_name)
            file_path.write_text(content, encoding="utf-8")
            return True
        except Exception as e:
            logger.error("Failed to save to Obsidian: %s", e)
            return False
        finally:
            self._lock_provider.release(lock_id)

    def backup(self, agent_name: str | None = None) -> str:
        """Create a timestamped backup inside the Obsidian vault."""
        self._check_registry(agent_name)
        file_path = self._get_obsidian_path(agent_name)
        if not file_path.exists():
            return "No memory to backup."
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rel_path = f"_memory/backups/{agent_name or 'global'}_{timestamp}.md"
        from deerflow.community.obsidian.tools import _resolve_obsidian_path
        backup_path = _resolve_obsidian_path(rel_path)
        
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(file_path, backup_path)
            
            # Retention: Delete oldest if > 10
            backups = sorted(backup_path.parent.glob(f"{agent_name or 'global'}_*.md"), key=os.path.getmtime)
            if len(backups) > 10:
                for old in backups[:-10]:
                    old.unlink()
                    
            return rel_path
        except Exception as e:
            return f"Backup failed: {str(e)}"


_storage_instance: MemoryStorage | None = None
_storage_lock = threading.Lock()


def get_memory_storage() -> MemoryStorage:
    """Get the memory storage instance with Explicit Registry validation."""
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance

    with _storage_lock:
        if _storage_instance is not None:
            return _storage_instance

        config = get_memory_config()
        storage_class_path = config.storage_class

        try:
            module_path, class_name = storage_class_path.rsplit(".", 1)
            import importlib
            module = importlib.import_module(module_path)
            storage_class = getattr(module, class_name)
            _storage_instance = storage_class()
        except Exception as e:
            logger.error("Fallback to FileMemoryStorage: %s", e)
            _storage_instance = FileMemoryStorage()

    return _storage_instance
