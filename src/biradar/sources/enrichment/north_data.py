"""North Data enrichment adapter."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from biradar.sources.enrichment.registry import register_enrichment_source
from biradar.sources.enrichment.runtime import _get_client

logger = logging.getLogger(__name__)

NORTH_DATA_BASE_URL = "https://www.northdata.de"


def lookup_north_data(company_name: str) -> dict[str, Any] | None:
    """Search North Data for public registry and sector metadata."""
    try:
        client = _get_client()
        search_resp = client.get(NORTH_DATA_BASE_URL, params={"query": company_name})
        search_resp.raise_for_status()
        search_soup = BeautifulSoup(search_resp.text, "html.parser")

        detail_href = None
        for link in search_soup.find_all("a", href=True):
            href = link.get("href")
            if href is None:
                continue
            if not href.startswith("/") or href.startswith("/_"):
                continue
            if href.count("/") < 2:
                continue
            detail_href = href
            break

        if not detail_href:
            return None

        detail_url = f"{NORTH_DATA_BASE_URL}{detail_href}"
        detail_resp = client.get(detail_url)
        detail_resp.raise_for_status()
        detail_soup = BeautifulSoup(detail_resp.text, "html.parser")

        registry_number = None
        title = detail_soup.title.get_text(strip=True) if detail_soup.title else ""
        registry_match = re.search(r"(HR[AB]\s*\d+\s*[A-Z]?)", title)
        if registry_match:
            registry_number = registry_match.group(1)

        sector = None
        for script in detail_soup.find_all("script", type="application/ld+json"):
            try:
                structured = json.loads(script.get_text())
            except json.JSONDecodeError:
                continue
            if structured.get("@type") == "BreadcrumbList":
                for item in structured.get("itemListElement", []):
                    name = item.get("item", {}).get("name")
                    if name and name != "Firmen":
                        sector = name
                        break
            if sector:
                break

        if not registry_number and not sector:
            return None

        return {
            "registry_number": registry_number,
            "sector": sector,
            "source": "north_data",
            "source_url": detail_url,
        }
    except Exception as exc:
        logger.warning("North Data lookup failed for '%s': %s", company_name, exc)
        return None


register_enrichment_source("north_data", lookup_north_data)
