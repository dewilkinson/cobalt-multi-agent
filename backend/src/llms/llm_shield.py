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

def _check_synthesis_ban():
    import time
    import json
    import os
    
    ban_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "synthesis_ban.json"))
    if os.path.exists(ban_file):
        try:
            with open(ban_file, "r") as f:
                ban_data = json.load(f)
            blocked_until = ban_data.get("blocked_until", 0)
            if time.time() < blocked_until:
                hours_left = (blocked_until - time.time()) / 3600
                fail_msg = f"[QUOTA_SHIELD] Report LLM synthesis is banned for the next {hours_left:.2f} hours (user-enforced)."
                logger.error(fail_msg)
                raise VLIQuotaExhaustedError(fail_msg)
        except VLIQuotaExhaustedError:
            raise
        except Exception as e:
            logger.warning(f"Error checking synthesis ban file: {e}")

def _swap_llm(runnable: Any, raw_llm: Any, wrapper: Any) -> Any:
    if runnable is raw_llm:
        return wrapper
    if hasattr(runnable, "bound") and runnable.bound is raw_llm:
        runnable.bound = wrapper
    elif hasattr(runnable, "steps"):
        for i, step in enumerate(runnable.steps):
            if step is raw_llm:
                runnable.steps[i] = wrapper
            else:
                _swap_llm(step, raw_llm, wrapper)
    if hasattr(runnable, "bound") and runnable.bound is not raw_llm:
        _swap_llm(runnable.bound, raw_llm, wrapper)
    return runnable

from langchain_core.runnables import Runnable

class QuotaProtectedLLM(Runnable):
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

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        bound = self.llm.bind_tools(tools, **kwargs)
        from langchain_core.runnables import RunnableBinding
        if isinstance(bound, RunnableBinding):
            return RunnableBinding(bound=self, kwargs=bound.kwargs, config=bound.config)
        return _swap_llm(bound, self.llm, self)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        runnable = self.llm.with_structured_output(schema, **kwargs)
        return _swap_llm(runnable, self.llm, self)

    def __or__(self, other: Any) -> Any:
        runnable = self.llm.__or__(other)
        return _swap_llm(runnable, self.llm, self)

    def __ror__(self, other: Any) -> Any:
        runnable = self.llm.__ror__(other)
        return _swap_llm(runnable, self.llm, self)

    async def ainvoke(
        self,
        input: Union[str, List[BaseMessage]],
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        # Check user-enforced synthesis ban
        _check_synthesis_ban()

        # Check daily quota limit
        from src.utils.quota_shield import get_daily_token_cap
        daily_cap = get_daily_token_cap()
        from src.utils.token_tracker import token_tracker
        total_used = token_tracker.get_total_daily_tokens()
        if total_used > daily_cap:
            fail_msg = f"[QUOTA_SHIELD] Daily token quota limit of {daily_cap:,} exceeded. Used today: {total_used}."
            logger.error(fail_msg)
            raise VLIQuotaExhaustedError(fail_msg)

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
        # Check user-enforced synthesis ban
        _check_synthesis_ban()

        # Check daily quota limit
        from src.utils.quota_shield import get_daily_token_cap
        daily_cap = get_daily_token_cap()
        from src.utils.token_tracker import token_tracker
        total_used = token_tracker.get_total_daily_tokens()
        if total_used > daily_cap:
            fail_msg = f"[QUOTA_SHIELD] Daily token quota limit of {daily_cap:,} exceeded. Used today: {total_used}."
            logger.error(fail_msg)
            raise VLIQuotaExhaustedError(fail_msg)

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

    async def abatch(
        self,
        inputs: List[Union[str, List[BaseMessage]]],
        config: Optional[Union[dict, List[dict]]] = None,
        **kwargs: Any,
    ) -> List[Any]:
        import asyncio
        if isinstance(config, list):
            tasks = [self.ainvoke(inp, config=cfg, **kwargs) for inp, cfg in zip(inputs, config)]
        else:
            tasks = [self.ainvoke(inp, config=config, **kwargs) for inp in inputs]
        return await asyncio.gather(*tasks)

    def batch(
        self,
        inputs: List[Union[str, List[BaseMessage]]],
        config: Optional[Union[dict, List[dict]]] = None,
        **kwargs: Any,
    ) -> List[Any]:
        results = []
        if isinstance(config, list):
            for inp, cfg in zip(inputs, config):
                results.append(self.invoke(inp, config=cfg, **kwargs))
        else:
            for inp in inputs:
                results.append(self.invoke(inp, config=config, **kwargs))
        return results

    # Note: For full coverage, especially when used in LangGraph, 
    # we should also ensure stream() and astream() are covered if used.
    # For now, ainvoke, invoke, batch, and abatch cover 90% of VLI usage.
