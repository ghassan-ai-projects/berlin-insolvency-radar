"""Bundesanzeiger enrichment adapter."""

from __future__ import annotations

import logging
import re
from typing import Any

from biradar.sources.enrichment.registry import register_enrichment_source
from biradar.sources.enrichment.runtime import _get_client

logger = logging.getLogger(__name__)

BUNDESANZEIGER_SEARCH_URL = "https://www.bundesanzeiger.de/pub/de/suchergebnis"


def lookup_bundesanzeiger(company_name: str) -> dict[str, Any] | None:
    """Search Bundesanzeiger for annual reports / balance sheets."""
    try:
        client = _get_client()
        params: dict[str, Any] = {
            "suchbegriff": company_name,
            "suchbereich": "alle",
        }
        resp = client.get(BUNDESANZEIGER_SEARCH_URL, params=params)
        resp.raise_for_status()
        html = resp.text

        annual_reports: list[str] = []
        balance_summary: str | None = None
        revenue_estimate: str | None = None

        if "Jahresabschluss" in html or "Jahresbericht" in html:
            years = re.findall(r"\b(20[1-2]\d)\b", html)
            unique_years = sorted(set(years))[:5]
            annual_reports = [f"Jahresabschluss {y}" for y in unique_years]

        if "Bilanz" in html:
            balance_summary = "Balance sheet data available"

        revenue_matches = re.findall(
            r"(?:Umsatz|Umsatzerlöse|Gesamtleistung)[^\d]*"
            r"([\d\s.,]+(?:Mio\.|Millionen|Mrd\.|Milliarden)?\s*(?:EUR|€))",
            html,
            re.I,
        )
        if revenue_matches:
            revenue_estimate = revenue_matches[0].strip()

        return {
            "annual_reports": annual_reports,
            "balance_summary": balance_summary,
            "revenue_estimate": revenue_estimate,
            "source": "bundesanzeiger",
        }
    except Exception as exc:
        logger.warning("Bundesanzeiger lookup failed for '%s': %s", company_name, exc)
        return None


register_enrichment_source("bundesanzeiger", lookup_bundesanzeiger)
