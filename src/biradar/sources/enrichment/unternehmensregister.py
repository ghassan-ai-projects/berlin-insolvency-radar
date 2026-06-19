"""Unternehmensregister enrichment adapter."""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from biradar.sources.enrichment.registry import (
    disable_source,
    register_enrichment_source,
)
from biradar.sources.enrichment.runtime import USER_AGENT, _get_client

logger = logging.getLogger(__name__)

UNTERNEHMENSREGISTER_BASE_URL = "https://www.unternehmensregister.de"
SEARCH_TOKEN_URL = f"{UNTERNEHMENSREGISTER_BASE_URL}/api/search-token"
REGISTER_PORTAL_URL = f"{UNTERNEHMENSREGISTER_BASE_URL}/de/registerPortal"
REGISTER_INFORMATION_FORM_TYPE = "REGISTER_INFORMATION"

LEGAL_FORMS = (
    "GmbH & Co. KG",
    "GmbH",
    "AG",
    "UG",
    "SE",
    "eG",
    "KG",
    "OHG",
)


def _normalize_name(value: str) -> str:
    normalized = value.casefold()
    normalized = normalized.replace("&", " und ")
    normalized = re.sub(r"[^a-z0-9äöüß]+", " ", normalized)
    return " ".join(normalized.split())


def _infer_legal_form(company_name: str) -> str | None:
    for legal_form in LEGAL_FORMS:
        if re.search(rf"\b{re.escape(legal_form)}\b", company_name, re.IGNORECASE):
            return legal_form
    return None


def _extract_balanced_json_array(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escape = False

    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    return None


def _decode_next_payload(raw_html: str) -> str:
    decoded = html_lib.unescape(raw_html)
    return decoded.replace(r"\"", '"').replace(r"\u0026", "&")


def _extract_register_companies(raw_html: str) -> list[dict[str, Any]]:
    """Extract company result objects from Unternehmensregister's Next/RSC payload."""
    decoded = _decode_next_payload(raw_html)
    companies: list[dict[str, Any]] = []
    marker = '"companies":['
    search_from = 0

    while True:
        marker_idx = decoded.find(marker, search_from)
        if marker_idx == -1:
            break

        array_start = marker_idx + len('"companies":')
        array_text = _extract_balanced_json_array(decoded, array_start)
        if array_text:
            try:
                parsed = json.loads(array_text)
            except json.JSONDecodeError:
                logger.debug("Failed to parse Unternehmensregister companies array")
            else:
                companies.extend(item for item in parsed if isinstance(item, dict))

        search_from = marker_idx + len(marker)

    return companies


def _select_best_company(
    companies: list[dict[str, Any]], company_name: str
) -> dict[str, Any] | None:
    if not companies:
        return None

    expected = _normalize_name(company_name)
    for company in companies:
        candidate_name = company.get("name")
        if (
            isinstance(candidate_name, str)
            and _normalize_name(candidate_name) == expected
        ):
            return company

    return companies[0]


def _format_registry_number(company: dict[str, Any]) -> str | None:
    register_number = company.get("registerNumber")
    if not register_number:
        return None

    register_type = company.get("registerType")
    if isinstance(register_type, dict):
        register_type_name = register_type.get("name")
        if register_type_name:
            return f"{register_type_name} {register_number}"

    return str(register_number)


def _format_registry_court(company: dict[str, Any]) -> str | None:
    register_court = company.get("registerCourt")
    if isinstance(register_court, dict):
        court_name = register_court.get("name")
        if court_name:
            return f"Amtsgericht {court_name}"
    return None


def _format_company_status(company: dict[str, Any]) -> str:
    if company.get("deletedFlag"):
        return "deleted"
    if company.get("changeFlag"):
        return "changed"
    return "active"


def _redact_search_token(url: object) -> str:
    parsed = urlsplit(str(url))
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key != "searchToken"
        ]
    )
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment)
    )


def _fetch_search_token() -> str | None:
    client = _get_client()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{UNTERNEHMENSREGISTER_BASE_URL}/de/search/register-information",
    }
    response = client.get(SEARCH_TOKEN_URL, headers=headers)
    if response.status_code in (400, 403, 423, 451):
        disable_source("unternehmensregister")
        logger.warning(
            "Unternehmensregister token endpoint returned %d; disabling for run",
            response.status_code,
        )
        return None
    response.raise_for_status()
    payload = response.json()
    token = payload.get("token")
    return token if isinstance(token, str) and token else None


def lookup_unternehmensregister(company_name: str) -> dict[str, Any] | None:
    """Search Unternehmensregister for company registration data."""
    try:
        token = _fetch_search_token()
        if not token:
            return None

        client = _get_client()
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{UNTERNEHMENSREGISTER_BASE_URL}/de/search/register-information",
        }
        response = client.get(
            REGISTER_PORTAL_URL,
            params={
                "companyName": company_name,
                "formType": REGISTER_INFORMATION_FORM_TYPE,
                "searchToken": token,
            },
            headers=headers,
        )
        if response.status_code in (400, 403, 423, 451):
            disable_source("unternehmensregister")
            logger.warning(
                "Unternehmensregister search returned %d; disabling for run",
                response.status_code,
            )
            return None
        response.raise_for_status()

        company = _select_best_company(
            _extract_register_companies(response.text), company_name
        )
        if company is None:
            return None

        result = {
            "source": "unternehmensregister",
            "source_url": _redact_search_token(response.url),
            "company_name": company.get("name"),
            "location": company.get("location"),
            "legal_form": _infer_legal_form(str(company.get("name") or company_name)),
            "registry_court": _format_registry_court(company),
            "registry_number": _format_registry_number(company),
            "company_status": _format_company_status(company),
            "status": _format_company_status(company),
            "euid": company.get("euid"),
            "last_update": company.get("lastUpdate"),
        }
        return {key: value for key, value in result.items() if value is not None}
    except Exception as exc:
        logger.warning(
            "Unternehmensregister lookup failed for '%s': %s", company_name, exc
        )
        return None


register_enrichment_source("unternehmensregister", lookup_unternehmensregister)
