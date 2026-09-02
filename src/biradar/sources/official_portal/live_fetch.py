"""Live portal search transport: session startup, retry loop, anti-bot gate."""

import asyncio
import logging
from datetime import date
from typing import Any

import httpx

from biradar.sources.official_portal.constants import build_search_headers
from biradar.sources.official_portal.jsf_session import (
    JSFSession,
    build_date_range_form_data,
)
from biradar.sources.official_portal.response_parsing import parse_response_details
from biradar.sources.official_portal.run_bookkeeping import persist_records

logger = logging.getLogger(__name__)


async def fetch_live_records(
    raw_record_repo,
    source_id: str,
    source_run_id: str,
    start_date: date,
    end_date: date,
    dry_run: bool,
) -> tuple[list[dict[str, Any]], int, int, list[str]]:
    """Search the live portal; returns (records, seen, imported, errors).

    On a failed session startup the records list stays empty and the failure
    is reported in errors — the run result then carries status "failed".
    """
    records: list[dict[str, Any]] = []
    records_seen = 0
    records_imported = 0
    errors: list[str] = []

    try:
        async with httpx.AsyncClient(
            headers=build_search_headers(), follow_redirects=True, timeout=30.0
        ) as client:
            session = JSFSession(client)
            await session.initialize()

            # Realistic delay to avoid anti-bot detection (async version)
            await asyncio.sleep(1.5)

            payload = session.get_payload(
                build_date_range_form_data(start_date, end_date)
            )
            records, records_seen, records_imported = await post_search_with_retry(
                client,
                session,
                payload,
                raw_record_repo,
                source_id,
                source_run_id,
                dry_run,
                errors,
            )

    except Exception as e:
        error_msg = f"Session initialization failed: {e!s}"
        logger.error(error_msg)
        errors.append(error_msg)

    return records, records_seen, records_imported, errors


async def post_search_with_retry(
    client: httpx.AsyncClient,
    session: JSFSession,
    payload: dict[str, Any],
    raw_record_repo,
    source_id: str,
    source_run_id: str,
    dry_run: bool,
    errors: list[str],
) -> tuple[list[dict[str, Any]], int, int]:
    """POST the search form, retrying timeouts, until a terminal outcome."""
    records: list[dict[str, Any]] = []
    records_seen = 0
    records_imported = 0

    # Retry logic for robustness
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await client.post(session.form_action, data=payload)

            # Handle Cloudflare or anti-bot 403
            if _is_anti_bot_response(response):
                logger.error(
                    "blocked_by_anti_bot", extra={"status_code": response.status_code}
                )
                errors.append("blocked_by_anti_bot")
                break

            response.raise_for_status()

            parsed = parse_response_details(response.text)
            if parsed.error_code:
                logger.error(parsed.error_code)
                errors.append(parsed.error_code)
                break

            records = parsed.records
            records_seen, records_imported = persist_records(
                raw_record_repo, source_id, source_run_id, records, dry_run
            )
            break  # Success, exit retry loop

        except httpx.TimeoutException:
            logger.warning(f"Timeout on attempt {attempt + 1}, retrying...")
            await asyncio.sleep(2.0 * (attempt + 1))
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code}"
            logger.error(error_msg)
            errors.append(error_msg)
            break
        except Exception as e:
            error_msg = f"Unexpected error: {e!s}"
            logger.error(error_msg)
            errors.append(error_msg)
            break

    return records, records_seen, records_imported


def _is_anti_bot_response(response: httpx.Response) -> bool:
    """Detect Cloudflare or generic anti-bot 403 challenges."""
    return response.status_code == 403 or "cloudflare" in response.text.lower()
