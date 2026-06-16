"""Unit tests for multi-source enrichment with mocked HTTP."""

import socket
from unittest.mock import patch

import pytest

from biradar.sources.enrichment import (
    EnrichmentResult,
    _aggregate_result,
    _build_company_slug,
    _dns_resolves,
    _get_enrichment_config,
    _reset_disabled_sources,
    enrich_candidate,
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
            lambda: type("Cfg", (), {"enabled": True, "delay_between_sources": 0.0})(),
        )

        with (
            patch("biradar.sources.enrichment.lookup_bundesanzeiger") as mock_b,
            patch("biradar.sources.enrichment.lookup_github") as mock_gh,
            patch("biradar.sources.enrichment.lookup_website") as mock_web,
        ):
            mock_b.return_value = {
                "annual_reports": ["Jahresabschluss 2025"],
                "balance_summary": "Balance sheet data available",
                "revenue_estimate": "1.2 Mio. EUR",
                "source": "bundesanzeiger",
            }
            mock_gh.return_value = {
                "org_name": "test-gmbh",
                "org_description": "A test company",
                "public_repos": 5,
                "stars": 10,
                "last_push": "2026-06-01",
                "language": ["Python", "TypeScript"],
                "source": "github",
            }
            mock_web.return_value = {
                "url": "https://test-gmbh.de",
                "title": "Test GmbH - Home",
                "description": "Innovative testing solutions",
                "tech_signals": ["React", "Node.js"],
                "status_code": 200,
                "source": "website",
            }

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
            lambda: type("Cfg", (), {"enabled": True, "delay_between_sources": 0.0})(),
        )

        with (
            patch("biradar.sources.enrichment.lookup_bundesanzeiger") as mock_b,
            patch("biradar.sources.enrichment.lookup_github") as mock_gh,
            patch("biradar.sources.enrichment.lookup_website") as mock_web,
        ):
            mock_b.side_effect = RuntimeError("Connection error")
            mock_gh.return_value = None
            mock_web.return_value = {
                "url": "https://example.de",
                "title": "Example",
                "description": "",
                "tech_signals": ["Docker"],
                "status_code": 200,
                "source": "website",
            }

            result = enrich_candidate("Example AG")

        assert result.enriched is True
        assert len(result.sources) == 1
        assert result.website_url == "https://example.de"
        assert len(result.errors) == 2

    def test_no_sources_return_data(self, monkeypatch):
        monkeypatch.setattr(
            "biradar.sources.enrichment._get_enrichment_config",
            lambda: type("Cfg", (), {"enabled": True, "delay_between_sources": 0.0})(),
        )

        with (
            patch(
                "biradar.sources.enrichment.lookup_bundesanzeiger", return_value=None
            ),
            patch("biradar.sources.enrichment.lookup_github", return_value=None),
            patch("biradar.sources.enrichment.lookup_website", return_value=None),
        ):
            result = enrich_candidate("Unknown GmbH")

        assert result.enriched is False
        assert len(result.sources) == 0
        assert len(result.errors) == 3


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
