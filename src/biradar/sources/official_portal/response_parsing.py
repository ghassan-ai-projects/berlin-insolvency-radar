"""Classification and parsing of complete portal responses (HTML and JSF)."""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

from biradar.sources.official_portal.html_parser import parse_html_results
from biradar.sources.official_portal.models import ParsedPortalResponse

logger = logging.getLogger(__name__)


def parse_response(html_or_xml: str) -> list[dict[str, Any]]:
    """Parse the portal response into raw record dictionaries."""
    return parse_response_details(html_or_xml).records


def parse_response_details(html_or_xml: str) -> ParsedPortalResponse:
    """Parse the portal response into records plus parser metadata."""
    try:
        sanitized = _strip_leading_comments(html_or_xml)
        if _looks_like_html_document(sanitized):
            parsed = parse_html_details(sanitized)
            logger.info(
                "Parsed %d records from HTML response via %s",
                len(parsed.records),
                parsed.parser_name,
            )
            return parsed

        parsed = parse_jsf_details(sanitized)
        logger.info(
            "Parsed %d records from JSF response via %s",
            len(parsed.records),
            parsed.parser_name,
        )
        return parsed
    except ET.ParseError as e:
        logger.error(f"Failed to parse JSF XML response: {e}")
        return ParsedPortalResponse([], "jsf_partial_parser", "parser_mismatch")
    except Exception as e:
        logger.error(f"Unexpected error parsing response: {e}")
        return ParsedPortalResponse([], "unknown_parser", "parser_mismatch")


def parse_html_details(sanitized: str) -> ParsedPortalResponse:
    """Parse a full HTML page into a classified portal response."""
    error_code = classify_portal_error(sanitized)
    if error_code:
        return ParsedPortalResponse([], "portal_error_parser", error_code)

    records = parse_html_results(sanitized)
    if records:
        return ParsedPortalResponse(records, "html_results_parser")

    if "Suchergebnis" in sanitized:
        return ParsedPortalResponse([], "html_results_parser", "parser_mismatch")
    return ParsedPortalResponse([], "html_results_parser")


def parse_jsf_details(sanitized: str) -> ParsedPortalResponse:
    """Parse a JSF partial response into a classified portal response."""
    records: list[dict[str, Any]] = []
    root = ET.fromstring(sanitized)
    for update in root.findall(".//update"):
        update_id = update.get("id", "")
        if "resultsTable" not in update_id and "results" not in update_id:
            continue
        cdata_content = update.text
        if not cdata_content:
            continue
        parsed = parse_html_details(cdata_content)
        if parsed.error_code:
            return parsed
        records.extend(parsed.records)

    if records:
        return ParsedPortalResponse(records, "jsf_partial_parser")
    return ParsedPortalResponse([], "jsf_partial_parser")


def classify_portal_error(sanitized: str) -> str | None:
    """Detect well-known portal error/result pages before generic parsing."""
    lowered = sanitized.lower()
    if "maximale trefferzahl beträgt" in lowered:
        return "too_many_results"
    if (
        "frm_suche" in sanitized
        and "jakarta.faces.ViewState" in sanitized
        and "Suchergebnis" not in sanitized
    ):
        return "search_form_returned_without_results"
    return None


def _strip_leading_comments(text: str) -> str:
    """Remove leading XML/HTML comments, which some portal responses prepend."""
    return re.sub(r"^\s*(<!--.*?-->\s*)+", "", text, flags=re.DOTALL)


def _looks_like_html_document(sanitized: str) -> bool:
    """Sniff whether a sanitized response is a full HTML document."""
    return (
        sanitized.lstrip().startswith("<!DOCTYPE html")
        or "<html" in sanitized[:512].lower()
    )
