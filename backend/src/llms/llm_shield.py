import logging
from typing import Any, List, Optional, Union, Dict
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from src.utils.quota_shield import quota_shield, VLIQuotaExhaustedError

logger = logging.getLogger(__name__)

class QuotaProtectedLLM:
    """
    A wrapper for LangChain ChatModels that intercepts calls to enforce 
    TPM/RPM quotas via QuotaShield.
    """
    def __init__(self, llm: BaseChatModel, tier: str):
        self.llm = llm
        self.tier = tier

    def __getattr__(self, name):
        """Delegate everything else to the internal LLM."""
        return getattr(self.llm, name)

    async def ainvoke(
        self,
        input: Union[str, List[BaseMessage]],
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        cache_name = None
        cleaned_input = input
        
        if isinstance(input, list):
            cleaned_input = []
            for msg in input:
                content = str(getattr(msg, 'content', msg))
                if "[CACHED_PAYLOAD:" in content:
                    import re
                    match = re.search(r"\[CACHED_PAYLOAD:\s*([^\]]+)\]", content)
                    if match:
                        cache_name = match.group(1).strip()
                        content = content.replace(match.group(0), "").strip()
                        # Avoid mutating immutable messages directly
                        try:
                            msg = msg.model_copy(update={"content": content})
                        except AttributeError:
                            msg = msg.copy(update={"content": content})
                cleaned_input.append(msg)
                
        llm_to_use = self.llm
        if cache_name and hasattr(self.llm, "cached_content"):
            logger.info(f"[CACHE_INTERCEPT] Routing invocation through native Gemini Cache: {cache_name}")
            try:
                llm_to_use = self.llm.model_copy(update={"cached_content": cache_name})
            except AttributeError:
                llm_to_use = self.llm.copy(update={"cached_content": cache_name})
                
        input_str = str(cleaned_input)
        estimated_input_tokens = len(input_str) // 4
        total_estimate = estimated_input_tokens + 1000 
        
        max_retries = 6
        base_delay = 2.0
        
        for attempt in range(max_retries):
            # 1. Check local shield
            if not quota_shield.allow_request(self.tier, total_estimate):
                if attempt == max_retries - 1:
                    fail_msg = f"[QUOTA_SHIELD] Request blocked for tier '{self.tier}'. Local limit reached after backoff."
                    logger.error(fail_msg)
                    raise VLIQuotaExhaustedError(fail_msg)
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[QUOTA_SHIELD] Local limit approached for '{self.tier}'. Backing off for {delay}s...")
                import asyncio
                await asyncio.sleep(delay)
                continue
                
            # 2. Execute
            try:
                result = await llm_to_use.ainvoke(cleaned_input, config, **kwargs)
                return result
            except Exception as e:
                e_str = (str(e) + " " + e.__class__.__name__).upper()
                is_quota = any(x in e_str for x in ["RESOURCE_EXHAUSTED", "429", "QUOTA_EXHAUSTED", "RATE_LIMIT", "TOO MANY REQUESTS"])
                
                if is_quota:
                    if attempt == max_retries - 1:
                        fail_msg = f"[QUOTA_SHIELD] Provider limit reached for tier '{self.tier}' after backoff: {e}"
                        logger.error(fail_msg)
                        raise VLIQuotaExhaustedError(fail_msg)
                    
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[QUOTA_SHIELD] Provider 429 for '{self.tier}'. Backing off for {delay}s...")
                    import asyncio
                    await asyncio.sleep(delay)
                else:
                    raise e
                    
        raise VLIQuotaExhaustedError(f"[QUOTA_SHIELD] Exhausted retries for {self.tier}")

    def invoke(
        self,
        input: Union[str, List[BaseMessage]],
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        cache_name = None
        cleaned_input = input
        
        if isinstance(input, list):
            cleaned_input = []
            for msg in input:
                content = str(getattr(msg, 'content', msg))
                if "[CACHED_PAYLOAD:" in content:
                    import re
                    match = re.search(r"\[CACHED_PAYLOAD:\s*([^\]]+)\]", content)
                    if match:
                        cache_name = match.group(1).strip()
                        content = content.replace(match.group(0), "").strip()
                        try:
                            msg = msg.model_copy(update={"content": content})
                        except AttributeError:
                            msg = msg.copy(update={"content": content})
                cleaned_input.append(msg)
                
        llm_to_use = self.llm
        if cache_name and hasattr(self.llm, "cached_content"):
            logger.info(f"[CACHE_INTERCEPT] Routing sync invocation through native Gemini Cache: {cache_name}")
            try:
                llm_to_use = self.llm.model_copy(update={"cached_content": cache_name})
            except AttributeError:
                llm_to_use = self.llm.copy(update={"cached_content": cache_name})
                
        input_str = str(cleaned_input)
        total_estimate = (len(input_str) // 4) + 1000
        
        max_retries = 6
        base_delay = 2.0
        
        for attempt in range(max_retries):
            if not quota_shield.allow_request(self.tier, total_estimate):
                if attempt == max_retries - 1:
                    fail_msg = f"[QUOTA_SHIELD] Request blocked for tier '{self.tier}'. Local limit reached after backoff."
                    logger.error(fail_msg)
                    raise VLIQuotaExhaustedError(fail_msg)
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[QUOTA_SHIELD] Local limit approached for '{self.tier}'. Sync backing off for {delay}s...")
                import time
                time.sleep(delay)
                continue
                
            try:
                return llm_to_use.invoke(cleaned_input, config, **kwargs)
            except Exception as e:
                e_str = (str(e) + " " + e.__class__.__name__).upper()
                is_quota = any(x in e_str for x in ["RESOURCE_EXHAUSTED", "429", "QUOTA_EXHAUSTED", "RATE_LIMIT", "TOO MANY REQUESTS"])
                
                if is_quota:
                    if attempt == max_retries - 1:
                        fail_msg = f"[QUOTA_SHIELD] Provider limit reached for tier '{self.tier}' after backoff: {e}"
                        logger.error(fail_msg)
                        raise VLIQuotaExhaustedError(fail_msg)
                    
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[QUOTA_SHIELD] Provider 429 for '{self.tier}'. Sync backing off for {delay}s...")
                    import time
                    time.sleep(delay)
                else:
                    raise e
                    
        raise VLIQuotaExhaustedError(f"[QUOTA_SHIELD] Exhausted retries for {self.tier}")

    # Note: For full coverage, especially when used in LangGraph, 
    # we should also ensure stream() and astream() are covered if used.
    # For now, ainvoke and invoke cover 90% of VLI usage.
