# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import pytest

from src.llms import llm


class DummyChatOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def invoke(self, msg):
        return f"Echo: {msg}"


@pytest.fixture(autouse=True)
def patch_chat_openai(monkeypatch):
    monkeypatch.setattr(llm, "ChatOpenAI", DummyChatOpenAI)


@pytest.fixture
def dummy_conf():
    return {
        "BASIC_MODEL": {"api_key": "test_key", "base_url": "http://test"},
        "REASONING_MODEL": {"api_key": "reason_key"},
        "VISION_MODEL": {"api_key": "vision_key"},
    }


def test_get_env_llm_conf(monkeypatch):
    # Clear any existing environment variables that might interfere
    monkeypatch.delenv("BASIC_MODEL__API_KEY", raising=False)
    monkeypatch.delenv("BASIC_MODEL__BASE_URL", raising=False)
    monkeypatch.delenv("BASIC_MODEL__MODEL", raising=False)

    monkeypatch.setenv("BASIC_MODEL__API_KEY", "env_key")
    monkeypatch.setenv("BASIC_MODEL__BASE_URL", "http://env")
    conf = llm._get_env_llm_conf("basic")
    assert conf["api_key"] == "env_key"
    assert conf["base_url"] == "http://env"


def test_create_llm_use_conf_merges_env(monkeypatch, dummy_conf):
    # Clear any existing environment variables that might interfere
    import os

    for key in list(os.environ.keys()):
        if "__" in key or key.endswith("_MODEL") or "GOOGLE" in key:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("BASIC_MODEL__BASE_URL", raising=False)
    monkeypatch.delenv("BASIC_MODEL__MODEL", raising=False)
    monkeypatch.setenv("BASIC_MODEL__API_KEY", "env_key")
    result = llm._create_llm_use_conf("basic", dummy_conf)
    assert isinstance(result, DummyChatOpenAI)
    assert result.kwargs["api_key"] == "env_key"
    assert result.kwargs["base_url"] == "http://test"


def test_create_llm_use_conf_invalid_type(monkeypatch, dummy_conf):
    # Clear any existing environment variables that might interfere
    monkeypatch.delenv("BASIC_MODEL__API_KEY", raising=False)
    monkeypatch.delenv("BASIC_MODEL__BASE_URL", raising=False)
    monkeypatch.delenv("BASIC_MODEL__MODEL", raising=False)

    with pytest.raises(ValueError):
        llm._create_llm_use_conf("unknown", dummy_conf)


def test_create_llm_use_conf_empty_conf(monkeypatch):
    # Clear any existing environment variables that might interfere
    monkeypatch.delenv("BASIC_MODEL__API_KEY", raising=False)
    monkeypatch.delenv("BASIC_MODEL__BASE_URL", raising=False)
    monkeypatch.delenv("BASIC_MODEL__MODEL", raising=False)

    with pytest.raises(ValueError):
        llm._create_llm_use_conf("basic", {})


def test_get_llm_by_type_caches(monkeypatch, dummy_conf):
    called = {}

    def fake_load_yaml_config(path):
        called["called"] = True
        return dummy_conf

    monkeypatch.setattr(llm, "load_yaml_config", fake_load_yaml_config)
    llm._llm_cache.clear()
    inst1 = llm.get_llm_by_type("basic")
    inst2 = llm.get_llm_by_type("basic")
    assert inst1 is inst2
    assert called["called"]


def test_quota_protected_llm_wrapper_and_ban(monkeypatch):
    import time
    import json
    from src.llms.llm_shield import QuotaProtectedLLM, VLIQuotaExhaustedError
    from langchain_core.runnables import Runnable, RunnableBinding

    class DummyModel(Runnable):
        def invoke(self, input, config=None, **kwargs):
            return "ok"
        def ainvoke(self, input, config=None, **kwargs):
            async def _run(): return "ok"
            return _run()
        def bind_tools(self, tools, **kwargs):
            return RunnableBinding(bound=self, kwargs={"tools": tools})
        def with_structured_output(self, schema, **kwargs):
            return self

    dummy_model = DummyModel()
    wrapped = QuotaProtectedLLM(dummy_model, "basic")

    # Verify standard invoke works when no ban is active
    monkeypatch.setattr("os.path.exists", lambda path: False)
    assert wrapped.invoke("test") == "ok"

    # Verify bind_tools returns a RunnableBinding that wraps QuotaProtectedLLM
    bound = wrapped.bind_tools(["tool1"])
    assert isinstance(bound, RunnableBinding)
    assert bound.bound is wrapped

    # Verify structured output keeps wrapper
    struct = wrapped.with_structured_output(dict)
    assert struct is wrapped

    # 2. Simulate synthesis ban active
    ban_data = {"blocked_until": time.time() + 100}
    import os
    
    def mock_exists(path):
        if "synthesis_ban.json" in path:
            return True
        return False
        
    class MockOpen:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): return json.dumps(ban_data)

    monkeypatch.setattr(os.path.exists, "__code__", mock_exists.__code__)
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: MockOpen())

    with pytest.raises(VLIQuotaExhaustedError):
        wrapped.invoke("test")
