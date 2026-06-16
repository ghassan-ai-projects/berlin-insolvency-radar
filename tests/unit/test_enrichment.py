"""Unit tests for multi-source enrichment with mocked HTTP."""

import os
from unittest.mock import MagicMock, patch

import pytest

from biradar.sources.enrichment import (
    EnrichmentResult,
    _aggregate_result,
    _build_company_slug,
    _dns_resolves,
    _is_enrich_real,
    enrich_candidate,
    lookup_github,
    lookup_handelsregister,
    lookup_website,
)


# ---------------------------------------------------------------------------
# Gate tests
# ---------------------------------------------------------------------------


class TestEnrichRealGate:
    def test_not_set_defaults_false(self, monkeypatch):
        monkeypatch.delenv("BI_RADAR_ENRICH_REAL", raising=False)
        assert _is_enrich_real() is False

    def test_zero_is_false(self, monkeypatch):
        monkeypatch.setenv("BI_RADAR_ENRICH_REAL", "0")
        assert _is_enrich_real() is False

    def test_false_string_is_false(self, monkeypatch):
        monkeypatch.setenv("BI_RADAR_ENRICH_REAL", "false")
        assert _is_enrich_real() is False

    def test_one_is_true(self, monkeypatch):
        monkeypatch.setenv("BI_RADAR_ENRICH_REAL", "1")
        assert _is_enrich_real() is True

    def test_true_string_is_true(self, monkeypatch):
        monkeypatch.setenv("BI_RADAR_ENRICH_REAL", "true")
        assert _is_enrich_real() is True


# ---------------------------------------------------------------------------
# enrich_candidate — mock mode
# ---------------------------------------------------------------------------


class TestEnrichCandidateMockMode:
    def test_returns_mock_when_disabled(self, monkeypatch):
        monkeypatch.setenv("BI_RADAR_ENRICH_REAL", "0")
        result = enrich_candidate("Test GmbH")
        assert result.enriched is True
        assert result.sector == "Unknown"
        assert len(result.sources) == 1
        assert result.sources[0]["value"] == "Unknown"

    def test_returns_mock_when_not_set(self, monkeypatch):
        monkeypatch.delenv("BI_RADAR_ENRICH_REAL", raising=False)
        result = enrich_candidate("Test GmbH")
        assert result.enriched is True
        assert result.sector == "Unknown"

    def test_empty_company_name(self):
        result = enrich_candidate("")
        assert result.enriched is False
        assert "Missing company_name" in result.errors


# ---------------------------------------------------------------------------
# enrich_candidate — real mode (mocked HTTP)
# ---------------------------------------------------------------------------


class TestEnrichCandidateRealMode:
    def test_all_sources_succeed(self, monkeypatch):
        monkeypatch.setenv("BI_RADAR_ENRICH_REAL", "1")

        with (
            patch("biradar.sources.enrichment.lookup_bundesanzeiger") as mock_b,
            patch("biradar.sources.enrichment.lookup_github") as mock_gh,
            patch("biradar.sources.enrichment.lookup_website") as mock_web,
            patch("biradar.sources.enrichment.lookup_handelsregister") as mock_hr,
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
                "title": "Test GmbH — Home",
                "description": "Innovative testing solutions",
                "tech_signals": ["React", "Node.js"],
                "status_code": 200,
                "source": "website",
            }
            mock_hr.return_value = {
                "legal_form": "GmbH",
                "registry_court": "Amtsgericht Berlin",
                "registry_number": "HRB 12345",
                "status": "active",
                "source": "handelsregister",
            }

            result = enrich_candidate("Test GmbH")

            assert result.enriched is True
            assert len(result.sources) == 4
            assert result.sector == "Legal form: GmbH"
            assert result.legal_form == "GmbH"
            assert result.registry_court == "Amtsgericht Berlin"
            assert result.registry_number == "HRB 12345"
            assert result.company_status == "active"
            assert result.tech_stack == "React, Node.js"
            assert result.website_url == "https://test-gmbh.de"
            assert result.github_org == "test-gmbh"
            assert "Revenue: 1.2 Mio. EUR" in (result.funding_info or "")
            assert len(result.errors) == 0

    def test_source_failure_isolation(self, monkeypatch):
        """One source failing should not abort the others."""
        monkeypatch.setenv("BI_RADAR_ENRICH_REAL", "1")

        with (
            patch("biradar.sources.enrichment.lookup_bundesanzeiger") as mock_b,
            patch("biradar.sources.enrichment.lookup_github") as mock_gh,
            patch("biradar.sources.enrichment.lookup_website") as mock_web,
            patch("biradar.sources.enrichment.lookup_handelsregister") as mock_hr,
        ):
            # Bundesanzeiger fails, Github returns None, website succeeds, HR succeeds
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
            mock_hr.return_value = {
                "legal_form": "AG",
                "registry_court": "Amtsgericht München",
                "registry_number": "HRB 99999",
                "status": "active",
                "source": "handelsregister",
            }

            result = enrich_candidate("Example AG")

            assert result.enriched is True
            assert len(result.sources) == 2  # only website + handelsregister
            assert result.legal_form == "AG"
            assert len(result.errors) == 2  # bundesanzeiger + github

    def test_no_sources_return_data(self, monkeypatch):
        """All sources returning None should still produce an enriched result."""
        monkeypatch.setenv("BI_RADAR_ENRICH_REAL", "1")

        with (
            patch("biradar.sources.enrichment.lookup_bundesanzeiger") as mock_b,
            patch("biradar.sources.enrichment.lookup_github") as mock_gh,
            patch("biradar.sources.enrichment.lookup_website") as mock_web,
            patch("biradar.sources.enrichment.lookup_handelsregister") as mock_hr,
        ):
            mock_b.return_value = None
            mock_gh.return_value = None
            mock_web.return_value = None
            mock_hr.return_value = None

            result = enrich_candidate("Unknown GmbH")

            assert result.enriched is True
            assert len(result.sources) == 0
            assert len(result.errors) == 4


# ---------------------------------------------------------------------------
# _aggregate_result
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _build_company_slug
# ---------------------------------------------------------------------------


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
        slug = _build_company_slug("SimpleName")
        assert slug == "simplename"


# ---------------------------------------------------------------------------
# _dns_resolves
# ---------------------------------------------------------------------------


class TestDnsResolves:
    def test_valid_domain(self):
        assert _dns_resolves("google.com") is True

    def test_invalid_domain(self):
        assert _dns_resolves("this-does-not-exist-xyzzy.invalid") is False


# ---------------------------------------------------------------------------
# EnrichmentResult pydantic model
# ---------------------------------------------------------------------------


class TestEnrichmentResult:
    def test_defaults(self):
        result = EnrichmentResult(company_name="Test")
        assert result.enriched is False
        assert result.sources == []
        assert result.errors == []

    def test_full_result(self):
        result = EnrichmentResult(
            company_name="Test GmbH",
            sources=[{"source": "handelsregister", "legal_form": "GmbH"}],
            errors=["bundesanzeiger: no data returned"],
            enriched=True,
            sector="Legal form: GmbH",
            legal_form="GmbH",
            tech_stack="React, Python",
            website_url="https://test.de",
            github_org="test-gmbh",
            funding_info="Revenue: 1.2 Mio. EUR",
            registry_court="Amtsgericht Berlin",
            registry_number="HRB 12345",
            company_status="active",
        )
        assert result.enriched is True
        assert result.legal_form == "GmbH"
        assert len(result.errors) == 1
