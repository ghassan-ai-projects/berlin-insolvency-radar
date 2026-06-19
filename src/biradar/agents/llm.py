"""Provider-neutral LLM configuration for agent calls."""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMRuntimeConfig:
    """Resolved runtime configuration for an OpenAI-compatible chat model."""

    provider: str
    api_key: str
    model: str
    timeout_seconds: float
    max_retries: int
    retry_backoff_seconds: float
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
    max_retries_raw = os.environ.get("BIRADAR_LLM_MAX_RETRIES", "1")
    backoff_raw = os.environ.get("BIRADAR_LLM_RETRY_BACKOFF_SECONDS", "1.5")
    timeout_seconds = float(timeout_raw)
    max_retries = max(0, int(max_retries_raw))
    retry_backoff_seconds = max(0.0, float(backoff_raw))

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
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
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
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
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


def classify_llm_exception(exc: Exception, error_prefix: str) -> str:
    """Classify an LLM failure into a stable runtime error code."""
    message = str(exc).lower()

    if isinstance(exc, TimeoutError | httpx.TimeoutException) or any(
        marker in message for marker in ("timed out", "timeout")
    ):
        return f"{error_prefix}_MODEL_TIMEOUT"

    if isinstance(exc, json.JSONDecodeError | ValidationError) or any(
        marker in message for marker in ("json", "validation", "response format")
    ):
        return f"{error_prefix}_MODEL_INVALID_RESPONSE"

    if any(
        marker in message
        for marker in (
            "401",
            "403",
            "unauthorized",
            "forbidden",
            "authentication",
            "invalid api key",
            "permission denied",
        )
    ):
        return f"{error_prefix}_MODEL_AUTH_ERROR"

    return f"{error_prefix}_MODEL_ERROR"


def should_retry_llm_exception(exc: Exception) -> bool:
    """Return whether an LLM failure is worth retrying."""
    message = str(exc).lower()
    return isinstance(
        exc,
        TimeoutError | httpx.TimeoutException | json.JSONDecodeError | ValidationError,
    ) or any(
        marker in message
        for marker in (
            "timed out",
            "timeout",
            "rate limit",
            "429",
            "502",
            "503",
            "504",
            "temporarily unavailable",
            "connection reset",
            "json",
            "validation",
        )
    )


def run_llm_operation[T](error_prefix: str, work: Callable[[], T]) -> T:
    """Run a bounded-retry LLM operation and raise classified runtime errors."""
    config = resolve_llm_config()
    total_attempts = config.max_retries + 1

    for attempt in range(1, total_attempts + 1):
        try:
            return work()
        except Exception as exc:
            error_code = classify_llm_exception(exc, error_prefix)
            if attempt < total_attempts and should_retry_llm_exception(exc):
                delay_seconds = round(config.retry_backoff_seconds * attempt, 2)
                logger.warning(
                    "%s attempt %d/%d failed with %s; retrying in %.2fs",
                    error_prefix,
                    attempt,
                    total_attempts,
                    error_code,
                    delay_seconds,
                )
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
                continue
            raise RuntimeError(error_code) from exc

    raise RuntimeError(f"{error_prefix}_MODEL_ERROR")
