"""Handelsregister enrichment adapter."""

from __future__ import annotations

import logging
import re

from biradar.sources.enrichment.registry import (
    disable_source,
    register_enrichment_source,
)
from biradar.sources.enrichment.runtime import USER_AGENT, _get_client

logger = logging.getLogger(__name__)

HANDELSREGISTER_SEARCH_URL = "https://www.handelsregister.de/rp_web/search.do"


def lookup_handelsregister(company_name: str) -> dict[str, str] | None:
    """Search the public Handelsregister portal for company registration data."""
    try:
        client = _get_client()
        params = {
            "suchbegriff": company_name,
            "registerArt": "alle",
        }
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = client.get(HANDELSREGISTER_SEARCH_URL, params=params, headers=headers)
        if resp.status_code in (400, 403):
            disable_source("handelsregister")
            logger.warning(
                "Handelsregister returned %d — disabling for remainder of run",
                resp.status_code,
            )
            return None
        resp.raise_for_status()
        html = resp.text

        legal_form = None
        registry_court = None
        registry_number = None
        status = None

        for form in [
            "GmbH & Co. KG",
            "GmbH",
            "AG",
            "UG",
            "SE",
            "e.V.",
            "KG",
            "OHG",
        ]:
            if re.search(rf"\b{re.escape(form)}\b", html):
                legal_form = form
                break

        court_match = re.search(
            r"(?:Amtsgericht|AG)\s+([A-ZÄÖÜ][a-zäöü]+(?:\s+[A-ZÄÖÜ][a-zäöü]+)*)",
            html,
        )
        if court_match:
            registry_court = court_match.group(0)

        reg_match = re.search(r"(HR[AB]\s*\d+\s*(?:[A-Z][a-z]+)?)", html)
        if reg_match:
            registry_number = reg_match.group(1)

        if "aktiv" in html.lower() or "active" in html.lower():
            status = "active"
        elif "gelöscht" in html.lower() or "löschung" in html.lower():
            status = "deleted"
        elif "aufgelöst" in html.lower():
            status = "dissolved"

        if not any([legal_form, registry_court, registry_number, status]):
            return None

        return {
            "legal_form": legal_form,
            "registry_court": registry_court,
            "registry_number": registry_number,
            "status": status,
            "source": "handelsregister",
        }
    except Exception as exc:
        logger.warning("Handelsregister lookup failed for '%s': %s", company_name, exc)
        return None


register_enrichment_source("handelsregister", lookup_handelsregister)
