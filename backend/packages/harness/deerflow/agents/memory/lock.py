# Cobalt Multiagent - High-fidelity financial analysis platform (Tiered Memory Storage)
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""Locking providers for memory storage."""

import abc
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional, Any

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    if sys.platform == "win32":
        import msvcrt

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class LockProvider(abc.ABC):
    """Abstract base class for lock providers."""

    @abc.abstractmethod
    def acquire(self, lock_id: str, timeout: float = 10.0) -> bool:
        """Acquire a lock."""
        pass

    @abc.abstractmethod
    def release(self, lock_id: str) -> None:
        """Release a lock."""
        pass


class FileLockProvider(LockProvider):
    """Filesystem-based lock provider using fcntl."""

    def __init__(self, lock_dir: Path):
        self._lock_dir = lock_dir
        self._locks: dict[str, Any] = {}

    def _get_lock_file(self, lock_id: str) -> Path:
        self._lock_dir.mkdir(parents=True, exist_ok=True)
        return self._lock_dir / f"{lock_id}.lock"

    def acquire(self, lock_id: str, timeout: float = 10.0) -> bool:
        lock_file = self._get_lock_file(lock_id)
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                f = open(lock_file, "w")
                if HAS_FCNTL:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                elif sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                self._locks[lock_id] = f
                return True
            except (IOError, OSError):
                if 'f' in locals() and f:
                    f.close()
                time.sleep(0.1)
        
        return False

    def release(self, lock_id: str) -> None:
        if lock_id in self._locks:
            f = self._locks.pop(lock_id)
            try:
                if HAS_FCNTL:
                    fcntl.flock(f, fcntl.LOCK_UN)
                elif sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                f.close()
            except (IOError, OSError):
                pass


class RedisLockProvider(LockProvider):
    """Redis-based distributed lock provider."""

    def __init__(self, redis_url: str):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis client not installed. Add 'redis' to dependencies.")
        self._client = redis.from_url(redis_url)
        self._locks: dict[str, str] = {}

    def acquire(self, lock_id: str, timeout: float = 10.0) -> bool:
        import uuid
        token = str(uuid.uuid4())
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self._client.set(f"lock:{lock_id}", token, nx=True, px=int(timeout * 1000)):
                self._locks[lock_id] = token
                return True
            time.sleep(0.1)
        
        return False

    def release(self, lock_id: str) -> None:
        if lock_id in self._locks:
            token = self._locks.pop(lock_id)
            # Use Lua script for atomic release (check token then delete)
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            self._client.eval(script, 1, f"lock:{lock_id}", token)


def get_lock_provider() -> LockProvider:
    """Get the configured lock provider."""
    from deerflow.config.memory_config import get_memory_config
    from deerflow.config.paths import get_paths
    
    config = get_memory_config()
    if config.lock_type == "redis" and config.redis_url:
        return RedisLockProvider(config.redis_url)
    
    return FileLockProvider(get_paths().shared_dir / ".locks")
