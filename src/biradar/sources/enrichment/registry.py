"""Registry and runtime state for enrichment sources."""

from __future__ import annotations

from biradar.sources.enrichment.models import (
    EnrichmentLookupFn,
    EnrichmentSourceDefinition,
)

_disabled_sources: set[str] = set()
_enrichment_source_registry: dict[str, EnrichmentSourceDefinition] = {}


def _reset_disabled_sources() -> None:
    """Clear the disabled-sources set (for test resets)."""
    _disabled_sources.clear()


def disable_source(name: str) -> None:
    """Disable a source for the remainder of the process."""
    _disabled_sources.add(name)


def is_source_disabled(name: str) -> bool:
    """Return whether a source is disabled for this process."""
    return name in _disabled_sources


def register_enrichment_source(
    name: str, lookup_fn: EnrichmentLookupFn
) -> EnrichmentSourceDefinition:
    """Register an enrichment lookup in execution order."""
    source = EnrichmentSourceDefinition(name=name, lookup_fn=lookup_fn)
    _enrichment_source_registry[name] = source
    return source


def get_registered_enrichment_sources() -> list[EnrichmentSourceDefinition]:
    """Return the registered enrichment sources in execution order."""
    return list(_enrichment_source_registry.values())
