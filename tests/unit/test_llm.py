"""Unit tests for provider-neutral LLM runtime configuration."""

import os
from types import SimpleNamespace

import pytest

from biradar.agents.llm import (
    DEFAULT_DEEPSEEK_BASE_URL,
    build_chat_llm,
    message_text,
    resolve_llm_config,
)


def test_resolve_llm_config_prefers_generic_provider_variables():
    original_values = {
        "BIRADAR_LLM_PROVIDER": os.environ.get("BIRADAR_LLM_PROVIDER"),
        "BIRADAR_LLM_API_KEY": os.environ.get("BIRADAR_LLM_API_KEY"),
        "BIRADAR_LLM_BASE_URL": os.environ.get("BIRADAR_LLM_BASE_URL"),
        "BIRADAR_LLM_MODEL": os.environ.get("BIRADAR_LLM_MODEL"),
        "BIRADAR_LLM_TIMEOUT_SECONDS": os.environ.get("BIRADAR_LLM_TIMEOUT_SECONDS"),
        "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY"),
    }
    os.environ["BIRADAR_LLM_PROVIDER"] = "openai"
    os.environ["BIRADAR_LLM_API_KEY"] = "generic-key"
    os.environ["BIRADAR_LLM_BASE_URL"] = "https://api.openai.com/v1"
    os.environ["BIRADAR_LLM_MODEL"] = "gpt-test"
    os.environ["BIRADAR_LLM_TIMEOUT_SECONDS"] = "12"
    os.environ["DEEPSEEK_API_KEY"] = "legacy-key"

    try:
        config = resolve_llm_config()
    finally:
        for name, value in original_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    assert config.provider == "openai"
    assert config.api_key == "generic-key"
    assert config.base_url == "https://api.openai.com/v1"
    assert config.model == "gpt-test"
    assert config.timeout_seconds == 12.0


def test_resolve_llm_config_falls_back_to_deepseek_variables():
    original_values = {
        "BIRADAR_LLM_PROVIDER": os.environ.get("BIRADAR_LLM_PROVIDER"),
        "BIRADAR_LLM_API_KEY": os.environ.get("BIRADAR_LLM_API_KEY"),
        "BIRADAR_LLM_BASE_URL": os.environ.get("BIRADAR_LLM_BASE_URL"),
        "BIRADAR_LLM_MODEL": os.environ.get("BIRADAR_LLM_MODEL"),
        "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY"),
        "DEEPSEEK_API_BASE": os.environ.get("DEEPSEEK_API_BASE"),
        "DEEPSEEK_MODEL": os.environ.get("DEEPSEEK_MODEL"),
        "DEEPSEEK_TIMEOUT_SECONDS": os.environ.get("DEEPSEEK_TIMEOUT_SECONDS"),
    }
    for name in (
        "BIRADAR_LLM_PROVIDER",
        "BIRADAR_LLM_API_KEY",
        "BIRADAR_LLM_BASE_URL",
        "BIRADAR_LLM_MODEL",
    ):
        os.environ.pop(name, None)
    os.environ["DEEPSEEK_API_KEY"] = "legacy-key"
    os.environ["DEEPSEEK_TIMEOUT_SECONDS"] = "18"

    try:
        config = resolve_llm_config()
    finally:
        for name, value in original_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    assert config.provider == "deepseek"
    assert config.api_key == "legacy-key"
    assert config.base_url == DEFAULT_DEEPSEEK_BASE_URL
    assert config.model == "deepseek-chat"
    assert config.timeout_seconds == 18.0


def test_resolve_llm_config_requires_model_for_generic_provider():
    original_values = {
        "BIRADAR_LLM_API_KEY": os.environ.get("BIRADAR_LLM_API_KEY"),
        "BIRADAR_LLM_MODEL": os.environ.get("BIRADAR_LLM_MODEL"),
        "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY"),
    }
    os.environ["BIRADAR_LLM_API_KEY"] = "generic-key"
    os.environ.pop("BIRADAR_LLM_MODEL", None)
    os.environ.pop("DEEPSEEK_API_KEY", None)

    try:
        with pytest.raises(RuntimeError, match="BIRADAR_LLM_MODEL"):
            resolve_llm_config()
    finally:
        for name, value in original_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_build_chat_llm_requests_json_object_response_format(monkeypatch):
    """AGENTS.md requires JSON output mode; every agent parses the reply as JSON."""
    monkeypatch.delenv("BIRADAR_LLM_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    llm = build_chat_llm()

    assert llm.model_kwargs["response_format"] == {"type": "json_object"}


def test_build_chat_llm_applies_resolved_model_and_timeout(monkeypatch):
    monkeypatch.setenv("BIRADAR_LLM_API_KEY", "generic-key")
    monkeypatch.setenv("BIRADAR_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("BIRADAR_LLM_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("BIRADAR_LLM_BASE_URL", "https://example.invalid/v1")

    llm = build_chat_llm()

    assert llm.model_name == "gpt-test"
    assert llm.temperature == 0.0
    assert llm.request_timeout == 12.0


def test_message_text_returns_plain_string_content():
    assert message_text(SimpleNamespace(content='{"ok": true}')) == '{"ok": true}'


def test_message_text_concatenates_content_blocks():
    """LangChain returns list content for block responses; str() would give a repr."""

    response = SimpleNamespace(
        content=[{"type": "text", "text": '{"a": '}, {"type": "text", "text": "1}"}]
    )

    assert message_text(response) == '{"a": 1}'


def test_message_text_handles_mixed_and_unknown_blocks():
    response = SimpleNamespace(
        content=["{", {"type": "image", "url": "x"}, {"type": "text", "text": "}"}]
    )

    assert message_text(response) == "{}"


def test_message_text_falls_back_to_str_when_no_content():
    assert message_text("raw string response") == "raw string response"


def test_message_text_block_output_is_json_parseable():
    """Guard the premise: the flattened form is what robust_json_parse needs."""
    from biradar.utils.prompts import robust_json_parse

    response = SimpleNamespace(
        content=[{"type": "text", "text": '{"company_name": '}, {"text": '"X"}'}]
    )

    assert robust_json_parse(message_text(response)) == {"company_name": "X"}
