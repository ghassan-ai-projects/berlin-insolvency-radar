"""Package entrypoints for multi-source company enrichment."""

from biradar.sources.enrichment.bundesanzeiger import lookup_bundesanzeiger
from biradar.sources.enrichment.github import lookup_github
from biradar.sources.enrichment.handelsregister import lookup_handelsregister
from biradar.sources.enrichment.models import (
    EnrichmentLookupFn,
    EnrichmentResult,
    EnrichmentSourceDefinition,
)
from biradar.sources.enrichment.north_data import lookup_north_data
from biradar.sources.enrichment.orchestrator import (
    _aggregate_result,
    _resolve_enrichment_sources,
    enrich_candidate,
)
from biradar.sources.enrichment.registry import (
    _reset_disabled_sources,
    get_registered_enrichment_sources,
    register_enrichment_source,
)
from biradar.sources.enrichment.runtime import (
    _close_client,
    _get_client,
    _get_enrichment_config,
)
from biradar.sources.enrichment.unternehmensregister import (
    lookup_unternehmensregister,
)
from biradar.sources.enrichment.website import (
    _build_company_slug,
    _dns_resolves,
    lookup_website,
)
from biradar.sources.enrichment.wikidata import lookup_wikidata

__all__ = [
    "EnrichmentLookupFn",
    "EnrichmentResult",
    "EnrichmentSourceDefinition",
    "_aggregate_result",
    "_build_company_slug",
    "_close_client",
    "_dns_resolves",
    "_get_client",
    "_get_enrichment_config",
    "_reset_disabled_sources",
    "_resolve_enrichment_sources",
    "enrich_candidate",
    "get_registered_enrichment_sources",
    "lookup_bundesanzeiger",
    "lookup_github",
    "lookup_handelsregister",
    "lookup_north_data",
    "lookup_unternehmensregister",
    "lookup_website",
    "lookup_wikidata",
    "register_enrichment_source",
]
