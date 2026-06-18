"""Unit tests for multi-source enrichment with mocked HTTP."""

import socket

import pytest

from biradar.sources.enrichment import (
    EnrichmentResult,
    EnrichmentSourceDefinition,
    _aggregate_result,
    _build_company_slug,
    _dns_resolves,
    _get_enrichment_config,
    _reset_disabled_sources,
    enrich_candidate,
    lookup_north_data,
    lookup_wikidata,
)


class TestEnrichmentConfig:
    def test_config_object_available(self):
        assert hasattr(_get_enrichment_config(), "enabled")


class TestEnrichCandidateModes:
    def test_returns_disabled_result_when_config_disabled(self, monkeypatch):
        _get_enrichment_config.cache_clear()
        monkeypatch.setattr(
            "biradar.sources.enrichment._get_enrichment_config",
            lambda: type("Cfg", (), {"enabled": False, "delay_between_sources": 0.0})(),
        )
        result = enrich_candidate("Test GmbH")
        assert result.enriched is False
        assert "disabled" in result.errors[0].lower()

    def test_empty_company_name(self):
        result = enrich_candidate("")
        assert result.enriched is False
        assert "Missing company_name" in result.errors


class TestEnrichCandidateLiveMode:
    @pytest.fixture(autouse=True)
    def _reset_sources(self):
        _reset_disabled_sources()

    def test_all_sources_succeed(self, monkeypatch):
        monkeypatch.setattr(
            "biradar.sources.enrichment._get_enrichment_config",
            lambda: type(
                "Cfg", (), {"enabled": True, "delay_between_sources": 0.0, "sources": {}}
            )(),
        )

        def mock_b(_company_name: str):
            return {
                "annual_reports": ["Jahresabschluss 2025"],
                "balance_summary": "Balance sheet data available",
                "revenue_estimate": "1.2 Mio. EUR",
                "source": "bundesanzeiger",
            }

        def mock_gh(_company_name: str):
            return {
                "org_name": "test-gmbh",
                "org_description": "A test company",
                "public_repos": 5,
                "stars": 10,
                "last_push": "2026-06-01",
                "language": ["Python", "TypeScript"],
                "source": "github",
            }

        def mock_web(_company_name: str):
            return {
                "url": "https://test-gmbh.de",
                "title": "Test GmbH - Home",
                "description": "Innovative testing solutions",
                "tech_signals": ["React", "Node.js"],
                "status_code": 200,
                "source": "website",
            }
        monkeypatch.setattr(
            "biradar.sources.enrichment._resolve_enrichment_sources",
            lambda: [
                EnrichmentSourceDefinition("bundesanzeiger", mock_b),
                EnrichmentSourceDefinition("github", mock_gh),
                EnrichmentSourceDefinition("website", mock_web),
            ],
        )

        result = enrich_candidate("Test GmbH")

        assert result.enriched is True
        assert len(result.sources) == 3
        assert result.tech_stack == "React, Node.js"
        assert result.website_url == "https://test-gmbh.de"
        assert result.website_status == 200
        assert result.github_org == "test-gmbh"
        assert result.funding_info == "Revenue: 1.2 Mio. EUR"
        assert len(result.errors) == 0

    def test_source_failure_isolation(self, monkeypatch):
        monkeypatch.setattr(
            "biradar.sources.enrichment._get_enrichment_config",
            lambda: type(
                "Cfg", (), {"enabled": True, "delay_between_sources": 0.0, "sources": {}}
            )(),
        )

        def failing_bundesanzeiger(_company_name: str):
            raise RuntimeError("Connection error")

        def empty_github(_company_name: str):
            return None

        def website_result(_company_name: str):
            return {
                "url": "https://example.de",
                "title": "Example",
                "description": "",
                "tech_signals": ["Docker"],
                "status_code": 200,
                "source": "website",
            }

        monkeypatch.setattr(
            "biradar.sources.enrichment._resolve_enrichment_sources",
            lambda: [
                EnrichmentSourceDefinition("bundesanzeiger", failing_bundesanzeiger),
                EnrichmentSourceDefinition("github", empty_github),
                EnrichmentSourceDefinition("website", website_result),
            ],
        )

        result = enrich_candidate("Example AG")

        assert result.enriched is True
        assert len(result.sources) == 1
        assert result.website_url == "https://example.de"
        assert len(result.errors) == 2

    def test_no_sources_return_data(self, monkeypatch):
        monkeypatch.setattr(
            "biradar.sources.enrichment._get_enrichment_config",
            lambda: type(
                "Cfg", (), {"enabled": True, "delay_between_sources": 0.0, "sources": {}}
            )(),
        )
        monkeypatch.setattr(
            "biradar.sources.enrichment._resolve_enrichment_sources",
            lambda: [
                EnrichmentSourceDefinition("bundesanzeiger", lambda _company_name: None),
                EnrichmentSourceDefinition("github", lambda _company_name: None),
                EnrichmentSourceDefinition("website", lambda _company_name: None),
            ],
        )

        result = enrich_candidate("Unknown GmbH")

        assert result.enriched is False
        assert len(result.sources) == 0
        assert len(result.errors) == 3

    def test_returns_clear_error_when_no_sources_enabled(self, monkeypatch):
        monkeypatch.setattr(
            "biradar.sources.enrichment._get_enrichment_config",
            lambda: type(
                "Cfg", (), {"enabled": True, "delay_between_sources": 0.0, "sources": {}}
            )(),
        )
        monkeypatch.setattr(
            "biradar.sources.enrichment._resolve_enrichment_sources", list
        )

        result = enrich_candidate("Unknown GmbH")

        assert result.enriched is False
        assert result.errors == ["No enrichment sources are enabled"]


class TestAggregateResult:
    def test_aggregates_all_sources(self):
        sources = [
            {
                "source": "handelsregister",
                "legal_form": "GmbH",
                "registry_court": "Amtsgericht Berlin",
                "registry_number": "HRB 123",
                "status": "active",
            },
            {
                "source": "website",
                "url": "https://example.de",
                "status_code": 200,
                "tech_signals": ["React", "AWS"],
            },
            {
                "source": "github",
                "org_name": "example-gmbh",
                "language": ["Python", "Go"],
            },
            {
                "source": "bundesanzeiger",
                "revenue_estimate": "5 Mio. EUR",
                "annual_reports": ["Jahresabschluss 2025"],
            },
        ]
        result = _aggregate_result(sources)
        assert result["sector"] == "Legal form: GmbH"
        assert result["legal_form"] == "GmbH"
        assert result["registry_court"] == "Amtsgericht Berlin"
        assert result["tech_stack"] == "React, AWS"
        assert result["website_url"] == "https://example.de"
        assert result["github_org"] == "example-gmbh"
        assert "Revenue: 5 Mio. EUR" in (result["funding_info"] or "")
        assert result["company_status"] == "active"

    def test_empty_sources(self):
        result = _aggregate_result([])
        assert result["sector"] is None
        assert result["tech_stack"] is None

    def test_aggregates_north_data_and_wikidata(self):
        sources = [
            {
                "source": "north_data",
                "registry_number": "HRB 555",
                "sector": "Software development",
            },
            {
                "source": "wikidata",
                "website_url": "https://example.org",
                "sector": "Artificial intelligence",
            },
        ]
        result = _aggregate_result(sources)
        assert result["registry_number"] == "HRB 555"
        assert result["sector"] == "Artificial intelligence"
        assert result["website_url"] == "https://example.org"


class TestBuildCompanySlug:
    def test_strips_gmbh(self):
        assert _build_company_slug("Test GmbH") == "test"

    def test_strips_ag(self):
        assert _build_company_slug("Example AG") == "example"

    def test_strips_ug(self):
        assert _build_company_slug("Startup UG") == "startup"

    def test_strips_gmbh_and_co_kg(self):
        assert _build_company_slug("Firma GmbH & Co. KG") == "firma"

    def test_preserves_hyphens(self):
        assert _build_company_slug("Müller & Söhne GmbH") == "mller-shne"

    def test_no_legal_form(self):
        assert _build_company_slug("Plain Name") == "plain-name"


class TestDnsResolves:
    def test_valid_domain(self, monkeypatch):
        def succeeds(*_args, **_kwargs):
            return [("ok",)]

        monkeypatch.setattr("biradar.sources.enrichment.socket.getaddrinfo", succeeds)
        assert _dns_resolves("example.com") is True

    def test_invalid_domain(self, monkeypatch):
        def fail(*_args, **_kwargs):
            raise socket.gaierror("dns failed")

        monkeypatch.setattr("biradar.sources.enrichment.socket.getaddrinfo", fail)
        assert _dns_resolves("does-not-exist.invalid") is False


class TestEnrichmentResult:
    def test_defaults(self):
        result = EnrichmentResult(company_name="Test GmbH")
        assert result.enriched is False
        assert result.sources == []
        assert result.errors == []

    def test_full_result(self):
        result = EnrichmentResult(
            company_name="Test GmbH",
            sources=[{"source": "website"}],
            errors=["minor issue"],
            enriched=True,
            sector="Tech",
            website_url="https://example.com",
        )
        assert result.enriched is True
        assert result.sector == "Tech"
        assert result.website_url == "https://example.com"


class TestAdditionalSources:
    def test_lookup_north_data_extracts_registry_fields(self, monkeypatch):
        class FakeResponse:
            def __init__(self, text: str):
                self.text = text

            def raise_for_status(self):
                return None

        class FakeClient:
            def get(self, url, params=None):
                if params is not None:
                    return FakeResponse(
                        """
                        <html><body>
                          <a href="/Example%20GmbH,%20Berlin/Amtsgericht%20Berlin%20HRB%2012345">Example GmbH</a>
                        </body></html>
                        """
                    )
                if "HRB%2012345" in url:
                    return FakeResponse(
                        """
                        <html>
                          <head><title>Example GmbH, Berlin, Amtsgericht Berlin HRB 12345: Netzwerk</title></head>
                          <body>
                            <script type="application/ld+json">
                              {"@type":"BreadcrumbList","itemListElement":[{"item":{"name":"Firmen"}},{"item":{"name":"Software publishing"}}]}
                            </script>
                          </body>
                        </html>
                        """
                    )
                raise AssertionError(f"Unexpected URL: {url}")

        monkeypatch.setattr(
            "biradar.sources.enrichment._get_client", lambda: FakeClient()
        )
        result = lookup_north_data("Example GmbH")
        assert result is not None
        assert result["registry_number"] == "HRB 12345"
        assert result["sector"] == "Software publishing"

    def test_lookup_wikidata_extracts_sector_and_website(self, monkeypatch):
        class FakeResponse:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        class FakeClient:
            def get(self, _url, params):
                action = params["action"]
                if action == "wbsearchentities":
                    return FakeResponse({"search": [{"id": "Q1"}]})
                if action == "wbgetentities" and params["ids"] == "Q1":
                    return FakeResponse(
                        {
                            "entities": {
                                "Q1": {
                                    "claims": {
                                        "P856": [
                                            {
                                                "mainsnak": {
                                                    "datavalue": {
                                                        "value": "https://example.org"
                                                    }
                                                }
                                            }
                                        ],
                                        "P452": [
                                            {
                                                "mainsnak": {
                                                    "datavalue": {"value": {"id": "Q2"}}
                                                }
                                            }
                                        ],
                                    }
                                }
                            }
                        }
                    )
                if action == "wbgetentities" and params["ids"] == "Q2":
                    return FakeResponse(
                        {
                            "entities": {
                                "Q2": {
                                    "labels": {
                                        "en": {"value": "Artificial intelligence"}
                                    }
                                }
                            }
                        }
                    )
                raise AssertionError(f"Unexpected params: {params}")

        monkeypatch.setattr(
            "biradar.sources.enrichment._get_client", lambda: FakeClient()
        )
        result = lookup_wikidata("Example GmbH")
        assert result is not None
        assert result["website_url"] == "https://example.org"
        assert result["sector"] == "Artificial intelligence"
