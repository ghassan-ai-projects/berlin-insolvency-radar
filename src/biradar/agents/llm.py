"""Provider-neutral LLM configuration for agent calls."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"


@dataclass(frozen=True)
class LLMRuntimeConfig:
    """Resolved runtime configuration for an OpenAI-compatible chat model."""

    provider: str
    api_key: str
    model: str
    timeout_seconds: float
    base_url: str | None = None


def resolve_llm_config() -> LLMRuntimeConfig:
    """Resolve provider-neutral LLM settings with DeepSeek fallback support."""
    provider = os.environ.get("BIRADAR_LLM_PROVIDER")
    api_key = os.environ.get("BIRADAR_LLM_API_KEY")
    base_url = os.environ.get("BIRADAR_LLM_BASE_URL")
    model = os.environ.get("BIRADAR_LLM_MODEL")
    timeout_raw = os.environ.get(
        "BIRADAR_LLM_TIMEOUT_SECONDS",
        os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "30"),
    )
    timeout_seconds = float(timeout_raw)

    if api_key:
        resolved_provider = provider or "openai_compatible"
        if not model:
            raise RuntimeError("BIRADAR_LLM_MODEL is required for generic LLM usage")
        return LLMRuntimeConfig(
            provider=resolved_provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
        )

    deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")
    if deepseek_api_key:
        return LLMRuntimeConfig(
            provider=provider or "deepseek",
            api_key=deepseek_api_key,
            base_url=base_url
            or os.environ.get("DEEPSEEK_API_BASE", DEFAULT_DEEPSEEK_BASE_URL),
            model=model or os.environ.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
            timeout_seconds=timeout_seconds,
        )

    raise RuntimeError(
        "BIRADAR_LLM_API_KEY or DEEPSEEK_API_KEY is required for LLM-backed agents"
    )


def build_chat_llm() -> ChatOpenAI:
    """Build the shared chat client for all agent calls."""
    config = resolve_llm_config()
    kwargs: dict[str, Any] = {
        "openai_api_key": config.api_key,
        "model": config.model,
        "temperature": 0.0,
        "timeout": config.timeout_seconds,
    }
    if config.base_url:
        kwargs["openai_api_base"] = config.base_url
    return ChatOpenAI(**kwargs)
