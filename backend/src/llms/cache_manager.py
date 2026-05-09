import logging
import datetime
from typing import Optional, Dict
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class GeminiCacheManager:
    """Manages the creation and lifecycle of Gemini Context Caches."""
    
    # Simple registry to keep track of active caches created in this session
    _active_caches: Dict[str, str] = {}
    
    @classmethod
    def create_session_cache(cls, model_name: str, system_instruction: str, large_payload: str, ttl_mins: int = 15, key: str = "default") -> Optional[str]:
        """Creates a cached context resource for massive payloads."""
        try:
            # Map standard model names to ones that definitely support caching
            cache_model = "gemini-3-pro-preview" if "pro" in model_name else "gemini-3-flash-preview"
            import os
            from src.llms.llm import _get_env_llm_conf
            conf = _get_env_llm_conf("basic")
            api_key = conf.get("api_key", os.environ.get("GEMINI_API_KEY"))
            
            # Using asyncio.to_thread or just synchronous call
            client = genai.Client(api_key=api_key)
            cached_content = client.caches.create(
                model=cache_model,
                config=types.CreateCachedContentConfig(
                    system_instruction=system_instruction,
                    contents=[large_payload],
                    ttl=f"{ttl_mins * 60}s"
                )
            )
            logger.info(f"[CACHE_MANAGER] Successfully created context cache {cached_content.name} for payload key '{key}' (TTL: {ttl_mins}m)")
            cls._active_caches[key] = cached_content.name
            return cached_content.name
        except Exception as e:
            logger.error(f"[CACHE_MANAGER] Failed to create cache for key '{key}': {e}")
            return None
            
    @classmethod
    def get_cache(cls, key: str) -> Optional[str]:
        """Returns the cache name for a given key, if active."""
        return cls._active_caches.get(key)
        
    @classmethod
    def cleanup_cache(cls, cache_name: str):
        """Deletes the cache to avoid storage charges."""
        try:
            import os
            from src.llms.llm import _get_env_llm_conf
            conf = _get_env_llm_conf("basic")
            api_key = conf.get("api_key", os.environ.get("GEMINI_API_KEY"))
            client = genai.Client(api_key=api_key)
            client.caches.delete(name=cache_name)
            logger.info(f"[CACHE_MANAGER] Successfully deleted cache {cache_name}")
            # Remove from tracking
            keys_to_remove = [k for k, v in cls._active_caches.items() if v == cache_name]
            for k in keys_to_remove:
                del cls._active_caches[k]
        except Exception as e:
            logger.error(f"[CACHE_MANAGER] Failed to delete cache {cache_name}: {e}")

    @classmethod
    def cleanup_all(cls):
        """Deletes all caches tracked by this manager."""
        caches_to_delete = list(cls._active_caches.values())
        for c in caches_to_delete:
            cls.cleanup_cache(c)
