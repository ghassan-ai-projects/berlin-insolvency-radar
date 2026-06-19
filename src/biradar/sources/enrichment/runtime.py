"""Runtime helpers for HTTP-backed enrichment sources."""

from __future__ import annotations

import logging
import ssl
import time
from functools import lru_cache

import httpx

from biradar.config.settings import get_settings, load_config

logger = logging.getLogger(__name__)

USER_AGENT: str = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
MAX_RETRIES: int = 3

_http_client: httpx.Client | None = None


@lru_cache(maxsize=1)
def _get_enrichment_config():
    settings = get_settings()
    return load_config(settings.project_root / "config").enrichment


def _get_client() -> httpx.Client:
    """Return a shared httpx Client (lazy-init)."""
    global _http_client
    if _http_client is None:
        config = _get_enrichment_config()
        _http_client = httpx.Client(
            timeout=httpx.Timeout(config.timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
    return _http_client


def _close_client() -> None:
    global _http_client
    if _http_client is not None:
        _http_client.close()
        _http_client = None


def _http_get(url: str) -> httpx.Response | None:
    """GET with retries. Returns response or None on final failure."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = _get_client()
            resp = client.get(url)
            if resp.status_code == 403:
                text_lower = (resp.text or "")[:2000].lower()
                if any(
                    marker in text_lower
                    for marker in (
                        "cloudflare",
                        "cf-challenge",
                        "captcha",
                        "access denied",
                    )
                ):
                    logger.debug("Anti-bot block fetching %s (skipping)", url)
                    return None
            resp.raise_for_status()
            return resp
        except httpx.TimeoutException as exc:
            logger.debug(
                "Timeout fetching %s (attempt %d/%d)", url, attempt, MAX_RETRIES
            )
            last_error = exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            logger.debug(
                "HTTP %s fetching %s (attempt %d/%d)",
                status,
                url,
                attempt,
                MAX_RETRIES,
            )
            if status in (403, 400):
                break
            last_error = exc
        except ssl.SSLError as exc:
            logger.debug("SSL error fetching %s (skipping): %s", url, exc)
            last_error = exc
            break
        except (httpx.ConnectError, ConnectionError, OSError) as exc:
            logger.debug(
                "Connection/network error fetching %s (skipping): %s", url, exc
            )
            last_error = exc
            break
        except httpx.RequestError as exc:
            logger.debug(
                "Request error fetching %s (attempt %d/%d): %s",
                url,
                attempt,
                MAX_RETRIES,
                exc,
            )
            last_error = exc

        if attempt < MAX_RETRIES:
            time.sleep(1.0)

    logger.warning("All %d retries exhausted for %s: %s", MAX_RETRIES, url, last_error)
    return None
