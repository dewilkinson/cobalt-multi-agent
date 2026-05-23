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

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
from pathlib import Path
from typing import Any, get_args

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from src.config import load_yaml_config
from src.config.agents import LLMType
from src.llms.providers.dashscope import ChatDashscope
from src.llms.llm_shield import QuotaProtectedLLM

# Cache for LLM instances
_llm_cache: dict[LLMType, BaseChatModel] = {}

import logging

logger = logging.getLogger(__name__)


def _get_config_file_path() -> str:
    """Get the path to the configuration file."""
    return str((Path(__file__).parent.parent.parent / "conf.yaml").resolve())


def _get_llm_type_config_keys() -> dict[str, str]:
    """Get mapping of LLM types to their configuration keys."""
    return {
        "reasoning": "REASONING_MODEL",
        "basic": "BASIC_MODEL",
        "vision": "VISION_MODEL",
        "code": "CODE_MODEL",
        "core": "CORE_MODEL",
        "legacy": "LEGACY_MODEL",
    }


def _get_env_llm_conf(llm_type: str) -> dict[str, Any]:
    """
    Get LLM configuration from environment variables.
    Environment variables should follow the format: {LLM_TYPE}__{KEY}
    e.g., BASIC_MODEL__api_key, BASIC_MODEL__base_url
    """
    prefix = f"{llm_type.upper()}_MODEL__"
    conf = {}
    for key, value in os.environ.items():
        if key.startswith(prefix):
            conf_key = key[len(prefix) :].lower()
            conf[conf_key] = value

    # Fallback: Use basic model credentials for vision if vision is unconfigured
    # Note: Gemini 1.5/2.5 Flash acts as a multimodal vision model out of the box
    if llm_type == "vision" and not conf:
        basic_prefix = "BASIC_MODEL__"
        for key, value in os.environ.items():
            if key.startswith(basic_prefix):
                conf_key = key[len(basic_prefix) :].lower()
                conf[conf_key] = value

    return conf


def _create_llm_use_conf(llm_type: LLMType, conf: dict[str, Any]) -> BaseChatModel:
    """Create LLM instance using configuration."""
    llm_type_config_keys = _get_llm_type_config_keys()
    config_key = llm_type_config_keys.get(llm_type)

    if not config_key:
        raise ValueError(f"Unknown LLM type: {llm_type}")

    llm_conf = conf.get(config_key, {})
    if not isinstance(llm_conf, dict):
        raise ValueError(f"Invalid LLM configuration for {llm_type}: {llm_conf}")

    # Get configuration from environment variables
    env_conf = _get_env_llm_conf(llm_type)

    # Merge configurations, with environment variables taking precedence
    merged_conf = {**llm_conf, **env_conf}

    if llm_type == "reasoning" and os.environ.get("BYPASS_REASONING_MODEL", "false").lower() == "true":
        logger.info(f"BYPASS_REASONING_MODEL is enabled. Forcing model to gemini-3-flash-preview for type: {llm_type}.")
        merged_conf["platform"] = "google_aistudio"
        merged_conf["model"] = "gemini-3-flash-preview"
        merged_conf.pop("thinking_level", None)
        merged_conf.pop("base_url", None)
        merged_conf.pop("api_base", None)

    if not merged_conf:
        raise ValueError(f"No configuration found for LLM type: {llm_type}")

    # Add max_retries to handle rate limit errors
    if "max_retries" not in merged_conf:
        merged_conf["max_retries"] = 3

    # Handle SSL verification settings
    verify_ssl = merged_conf.pop("verify_ssl", True)

    # Create custom HTTP client if SSL verification is disabled
    if not verify_ssl:
        http_client = httpx.Client(verify=False)
        http_async_client = httpx.AsyncClient(verify=False)
        merged_conf["http_client"] = http_client
        merged_conf["http_async_client"] = http_async_client

    # Check if it's Google AI Studio platform based on configuration
    platform = merged_conf.get("platform", "").lower()
    is_google_aistudio = platform == "google_aistudio" or platform == "google-aistudio"
    is_ollama = platform == "ollama"

    if is_ollama:
        # Standard Ollama OpenAI-compatible endpoint
        ollama_conf = merged_conf.copy()
        ollama_conf["base_url"] = ollama_conf.get("base_url", "http://localhost:11434/v1")
        # Ollama doesn't need an API key for local use, but the client expects one
        ollama_conf["api_key"] = ollama_conf.get("api_key", "ollama")
        ollama_conf.pop("platform", None)

        logger.info(f"LLM Tool: Initializing Ollama model '{ollama_conf.get('model')}' (Type: {llm_type})")
        return ChatOpenAI(**ollama_conf)

    if is_google_aistudio:
        # Handle Google AI Studio specific configuration
        gemini_conf = merged_conf.copy()

        # [RELIABILITY] Fast-Fail for all tiers to trigger tiered fallback immediately.
        # Otherwise, the SDK sits for 60s+ retrying while the user waits.
        # [HARDENING] timeout=30 prevents internal SDK hangs on 429
        gemini_conf["max_retries"] = 0
        gemini_conf["timeout"] = 30

        # [RELIABILITY] Fallback to BASIC_MODEL__api_key if this specific tier (e.g. legacy) lacks one
        key_val = gemini_conf.get("api_key", "")
        if not key_val:
            key_val = os.environ.get(f"{llm_type.upper()}_MODEL__API_KEY", 
                    os.environ.get("BASIC_MODEL__api_key", os.environ.get("GEMINI_API_KEY", "")))
            if key_val:
                gemini_conf["api_key"] = key_val

        # Map common keys to Google AI Studio specific keys
        if "api_key" in gemini_conf and gemini_conf["api_key"]:
            # Mirror both keys for cross-version SDK compatibility
            gemini_conf["google_api_key"] = gemini_conf["api_key"]
            gemini_conf["api_key"] = gemini_conf["api_key"]
        else:
            raise ValueError(f"LLM Tool: Mission-critical API key missing for Gemini {llm_type}. "
                             f"Configure {llm_type.upper()}_MODEL__API_KEY in .env.")

        # Remove base_url and platform since Google AI Studio doesn't use them
        gemini_conf.pop("base_url", None)
        gemini_conf.pop("platform", None)

        # Remove unsupported parameters for Google AI Studio
        gemini_conf.pop("http_client", None)
        gemini_conf.pop("http_async_client", None)

        # [RELIABILITY] Exact model name logging for VLI SMC Stabilization
        model_name = gemini_conf.get("model", "unknown")
        logger.info(f"LLM Tool: Initializing Gemini model '{model_name}' (Type: {llm_type})")

        # [NEW] Support Gemini 3 'thinking_level' parameter
        if llm_type == "reasoning" and "thinking_level" in merged_conf:
            gemini_conf["thinking_level"] = merged_conf["thinking_level"]
            # Recommended temperature for reasoning models
            if "temperature" not in gemini_conf:
                gemini_conf["temperature"] = 1.0

        # [RELIABILITY] Disable safety constraints that cause Empty String Crypto generation
        from langchain_google_genai import HarmCategory, HarmBlockThreshold

        gemini_conf["safety_settings"] = {
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY: HarmBlockThreshold.BLOCK_NONE,
        }

        try:
            return ChatGoogleGenerativeAI(**gemini_conf)
        except Exception as e:
            logger.error(f"LLM Tool: Failed to initialize Gemini '{model_name}': {e}")
            if "not found" in str(e).lower() and not model_name.startswith("models/"):
                retry_name = f"models/{model_name}"
                logger.info(f"LLM Tool: Retrying with prefix '{retry_name}'...")
                gemini_conf["model"] = retry_name
                return ChatGoogleGenerativeAI(**gemini_conf)
            raise e

    if "azure_endpoint" in merged_conf or os.getenv("AZURE_OPENAI_ENDPOINT"):
        return AzureChatOpenAI(**merged_conf)

    # Check if base_url is dashscope endpoint
    if "base_url" in merged_conf and "dashscope." in merged_conf["base_url"]:
        if llm_type == "reasoning":
            merged_conf["extra_body"] = {"enable_thinking": True}
        else:
            merged_conf["extra_body"] = {"enable_thinking": False}
        return ChatDashscope(**merged_conf)

    if llm_type == "reasoning":
        merged_conf["api_base"] = merged_conf.pop("base_url", None)
        return ChatDeepSeek(**merged_conf)
    else:
        return ChatOpenAI(**merged_conf)


def get_llm_by_type(llm_type: LLMType) -> BaseChatModel:
    """
    Get LLM instance by type.
    """
    global _llm_cache
    if llm_type in _llm_cache:
        return _llm_cache[llm_type]

    conf = load_yaml_config(_get_config_file_path())
    llm = _create_llm_use_conf(llm_type, conf)
    
    # [NEW] Attach Token Tracker Callback
    from src.utils.token_tracker import TokenUsageCallbackHandler
    if not llm.callbacks:
        llm.callbacks = []
    llm.callbacks.append(TokenUsageCallbackHandler())
    
    # [SAFETY] Wrap the LLM in the Quota Shield
    protected_llm = QuotaProtectedLLM(llm, llm_type)
    
    _llm_cache[llm_type] = protected_llm
    return protected_llm


def get_configured_llm_models() -> dict[str, list[str]]:
    """
    Get all configured LLM models grouped by type.

    Returns:
        Dictionary mapping LLM type to list of configured model names.
    """
    try:
        conf = load_yaml_config(_get_config_file_path())
        llm_type_config_keys = _get_llm_type_config_keys()

        configured_models: dict[str, list[str]] = {}

        for llm_type in get_args(LLMType):
            # Get configuration from YAML file
            config_key = llm_type_config_keys.get(llm_type, "")
            yaml_conf = conf.get(config_key, {}) if config_key else {}

            # Get configuration from environment variables
            env_conf = _get_env_llm_conf(llm_type)

            # Merge configurations, with environment variables taking precedence
            merged_conf = {**yaml_conf, **env_conf}

            # Check if model is configured
            model_name = merged_conf.get("model")
            if model_name:
                configured_models.setdefault(llm_type, []).append(model_name)

        return configured_models

    except Exception as e:
        # Log error and return empty dict to avoid breaking the application
        print(f"Warning: Failed to load LLM configuration: {e}")
        return {}


# In the future, we will use reasoning_llm and vl_llm for different purposes
# reasoning_llm = get_llm_by_type("reasoning")
# vl_llm = get_llm_by_type("vision")
