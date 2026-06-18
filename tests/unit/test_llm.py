"""Unit tests for provider-neutral LLM runtime configuration."""

import os

import pytest

from biradar.agents.llm import DEFAULT_DEEPSEEK_BASE_URL, resolve_llm_config


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
