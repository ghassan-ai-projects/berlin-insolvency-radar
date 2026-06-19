"""Wikidata enrichment adapter."""

from __future__ import annotations

import logging
from typing import Any

from biradar.sources.enrichment.registry import register_enrichment_source
from biradar.sources.enrichment.runtime import _get_client

logger = logging.getLogger(__name__)

WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"


def _resolve_wikidata_entity_label(entity_id: str) -> str | None:
    """Resolve a Wikidata entity label in German or English."""
    client = _get_client()
    resp = client.get(
        WIKIDATA_API_URL,
        params={
            "action": "wbgetentities",
            "ids": entity_id,
            "props": "labels",
            "languages": "de|en",
            "format": "json",
        },
    )
    resp.raise_for_status()
    entity = resp.json().get("entities", {}).get(entity_id, {})
    labels = entity.get("labels", {})
    return labels.get("de", {}).get("value") or labels.get("en", {}).get("value")


def lookup_wikidata(company_name: str) -> dict[str, Any] | None:
    """Search Wikidata for public website and industry metadata."""
    try:
        client = _get_client()
        search_resp = client.get(
            WIKIDATA_API_URL,
            params={
                "action": "wbsearchentities",
                "search": company_name,
                "language": "de",
                "type": "item",
                "limit": 1,
                "format": "json",
            },
        )
        search_resp.raise_for_status()
        search_results = search_resp.json().get("search", [])
        if not search_results:
            return None

        entity_id = search_results[0].get("id")
        if not entity_id:
            return None

        entity_resp = client.get(
            WIKIDATA_API_URL,
            params={
                "action": "wbgetentities",
                "ids": entity_id,
                "props": "claims",
                "format": "json",
            },
        )
        entity_resp.raise_for_status()
        claims = (
            entity_resp.json().get("entities", {}).get(entity_id, {}).get("claims", {})
        )

        website_url = None
        if "P856" in claims:
            website_claim = claims["P856"][0]
            website_url = (
                website_claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            )

        sector = None
        if "P452" in claims:
            industry_claim = claims["P452"][0]
            industry_value = (
                industry_claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            )
            industry_entity_id = industry_value.get("id")
            if industry_entity_id:
                sector = _resolve_wikidata_entity_label(industry_entity_id)

        if not website_url and not sector:
            return None

        return {
            "website_url": website_url,
            "sector": sector,
            "source": "wikidata",
            "source_url": f"https://www.wikidata.org/wiki/{entity_id}",
        }
    except Exception as exc:
        logger.warning("Wikidata lookup failed for '%s': %s", company_name, exc)
        return None


register_enrichment_source("wikidata", lookup_wikidata)
