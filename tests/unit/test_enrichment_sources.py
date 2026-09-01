"""Unit tests for the individual enrichment source adapters with mocked HTTP."""

import json
import ssl
from types import SimpleNamespace

import httpx
import pytest

from biradar.sources.enrichment import (
    EnrichmentSourceDefinition,
    _aggregate_result,
    _reset_disabled_sources,
    _resolve_enrichment_sources,
    enrich_candidate,
    get_registered_enrichment_sources,
    lookup_bundesanzeiger,
    lookup_github,
    lookup_handelsregister,
    lookup_north_data,
    lookup_unternehmensregister,
    lookup_website,
    lookup_wikidata,
)
from biradar.sources.enrichment import runtime as enrichment_runtime
from biradar.sources.enrichment.registry import disable_source, is_source_disabled
from biradar.sources.enrichment.runtime import (
    _get_source_config,
    _http_get,
    source_delay_seconds,
    source_timeout_seconds,
)
from biradar.sources.enrichment.unternehmensregister import (
    _extract_balanced_json_array,
    _extract_register_companies,
    _format_company_status,
    _format_registry_court,
    _format_registry_number,
    _infer_legal_form,
    _select_best_company,
)
from biradar.sources.enrichment.website import _build_company_slug


class FakeResponse:
    """Stub httpx.Response with a configurable status, body, and JSON payload."""

    def __init__(self, status_code: int = 200, text: str = "", payload=None):
        self.status_code = status_code
        self.text = text
        self.payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.com")
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=request, response=self
            )

    def json(self):
        return self.payload


class BrokenTextResponse:
    """Response whose body access fails, as with an interrupted stream."""

    def __init__(self, status_code: int = 200):
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    @property
    def text(self) -> str:
        raise RuntimeError("response stream closed")


class FakeClient:
    """Stub httpx.Client routing GETs through a handler and recording calls."""

    def __init__(self, handler):
        self.handler = handler
        self.calls: list[str] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(url)
        return self.handler(url, params, headers, timeout)


def _install_client(monkeypatch, module: str, handler) -> FakeClient:
    client = FakeClient(handler)
    monkeypatch.setattr(
        f"biradar.sources.enrichment.{module}._get_client", lambda: client
    )
    return client


@pytest.fixture(autouse=True)
def _reset_sources():
    _reset_disabled_sources()
    yield
    _reset_disabled_sources()


class TestBundesanzeigerLookup:
    def test_lookup_bundesanzeiger_parses_reports_balance_and_revenue(
        self, monkeypatch
    ):
        html = """<html><body>
            <div>Jahresabschluss 2019</div>
            <div>Jahresabschluss 2021</div>
            <div>Jahresabschluss 2018</div>
            <div>Jahresabschluss 2018</div>
            <div>Jahresabschluss 2015</div>
            <div>Jahresabschluss 2020</div>
            <div>Jahresabschluss 2013</div>
            <div>Bilanz sowie GuV</div>
            <div>Umsatzerlöse: 1,2 Mio. EUR</div>
        </body></html>"""
        _install_client(
            monkeypatch,
            "bundesanzeiger",
            lambda *_args: FakeResponse(200, html),
        )

        result = lookup_bundesanzeiger("Test GmbH")

        assert result is not None
        assert result["source"] == "bundesanzeiger"
        assert result["annual_reports"] == [
            "Jahresabschluss 2013",
            "Jahresabschluss 2015",
            "Jahresabschluss 2018",
            "Jahresabschluss 2019",
            "Jahresabschluss 2020",
        ]
        assert result["balance_summary"] == "Balance sheet data available"
        assert result["revenue_estimate"] == "1,2 Mio. EUR"

    def test_lookup_bundesanzeiger_returns_empty_fields_without_markers(
        self, monkeypatch
    ):
        _install_client(
            monkeypatch,
            "bundesanzeiger",
            lambda *_args: FakeResponse(200, "<html><body><p>Hallo</p></body></html>"),
        )

        result = lookup_bundesanzeiger("Test GmbH")

        assert result == {
            "annual_reports": [],
            "balance_summary": None,
            "revenue_estimate": None,
            "source": "bundesanzeiger",
        }

    def test_lookup_bundesanzeiger_returns_none_when_client_raises(self, monkeypatch):
        def handler(*_args):
            raise httpx.ConnectError("no route to host")

        _install_client(monkeypatch, "bundesanzeiger", handler)

        assert lookup_bundesanzeiger("Test GmbH") is None


class TestGithubLookup:
    def test_lookup_github_returns_org_details_from_three_requests(self, monkeypatch):
        def handler(url, _params, _headers, _timeout):
            if url.endswith("/search/users"):
                return FakeResponse(200, payload={"items": [{"login": "testcorp"}]})
            if url.endswith("/orgs/testcorp/repos"):
                return FakeResponse(
                    200,
                    payload=[
                        {
                            "stargazers_count": 3,
                            "pushed_at": "2026-01-15",
                            "language": "Python",
                        },
                        {
                            "stargazers_count": 9,
                            "pushed_at": "2025-05-01",
                            "language": "Go",
                        },
                        {
                            "stargazers_count": 1,
                            "pushed_at": "2026-03-01",
                            "language": None,
                        },
                    ],
                )
            if url.endswith("/orgs/testcorp"):
                return FakeResponse(
                    200,
                    payload={"description": "A test org", "public_repos": 7},
                )
            raise AssertionError(f"Unexpected URL: {url}")

        client = _install_client(monkeypatch, "github", handler)

        result = lookup_github("Test GmbH")

        assert len(client.calls) == 3
        assert result is not None
        assert result["org_name"] == "testcorp"
        assert result["org_description"] == "A test org"
        assert result["public_repos"] == 7
        assert result["stars"] == 13
        assert result["last_push"] == "2026-03-01"
        assert sorted(result["language"]) == ["Go", "Python"]
        assert result["source"] == "github"

    def test_lookup_github_returns_none_when_search_has_no_items(self, monkeypatch):
        _install_client(
            monkeypatch,
            "github",
            lambda *_args: FakeResponse(200, payload={"items": []}),
        )

        assert lookup_github("Test GmbH") is None

    def test_lookup_github_returns_none_when_item_has_no_login(self, monkeypatch):
        _install_client(
            monkeypatch,
            "github",
            lambda *_args: FakeResponse(200, payload={"items": [{"label": "x"}]}),
        )

        assert lookup_github("Test GmbH") is None

    def test_lookup_github_sleeps_and_retries_on_rate_limit(self, monkeypatch):
        sleeps: list[float] = []
        monkeypatch.setattr(
            "biradar.sources.enrichment.github.time.sleep",
            lambda seconds: sleeps.append(seconds),
        )
        search_calls = {"count": 0}

        def handler(url, _params, _headers, _timeout):
            if url.endswith("/search/users"):
                search_calls["count"] += 1
                if search_calls["count"] == 1:
                    return FakeResponse(403, text="API rate limit exceeded")
                return FakeResponse(200, payload={"items": [{"login": "testcorp"}]})
            if url.endswith("/orgs/testcorp"):
                return FakeResponse(
                    200, payload={"description": None, "public_repos": 2}
                )
            if url.endswith("/orgs/testcorp/repos"):
                return FakeResponse(200, payload=[])
            raise AssertionError(f"Unexpected URL: {url}")

        _install_client(monkeypatch, "github", handler)

        result = lookup_github("Test GmbH")

        assert search_calls["count"] == 2
        assert sleeps == [60]
        assert result is not None
        assert result["stars"] == 0
        assert result["last_push"] is None
        assert result["language"] is None

    def test_lookup_github_returns_none_when_client_raises(self, monkeypatch):
        def handler(*_args):
            raise httpx.ConnectError("dns failure")

        _install_client(monkeypatch, "github", handler)

        assert lookup_github("Test GmbH") is None


class TestHandelsregisterLookup:
    def test_lookup_handelsregister_extracts_registration_fields(self, monkeypatch):
        html = """<html><body>
            <h1>Firma Test GmbH, Amtsgericht Charlottenburg</h1>
            <div>Registernummer: HRB 12345</div>
            <div>Status: aktiv</div>
        </body></html>"""
        _install_client(
            monkeypatch, "handelsregister", lambda *_args: FakeResponse(200, html)
        )

        result = lookup_handelsregister("Test GmbH")

        assert result == {
            "legal_form": "GmbH",
            "registry_court": "Amtsgericht Charlottenburg",
            "registry_number": "HRB 12345",
            "status": "active",
            "source": "handelsregister",
        }

    @pytest.mark.parametrize(
        ("html", "status"),
        [
            ("<html><body><p>gelöscht</p></body></html>", "deleted"),
            ("<html><body><p>Löschung beantragt</p></body></html>", "deleted"),
            ("<html><body><p>aufgelöst</p></body></html>", "dissolved"),
        ],
    )
    def test_lookup_handelsregister_classifies_status_markers(
        self, monkeypatch, html, status
    ):
        _install_client(
            monkeypatch, "handelsregister", lambda *_args: FakeResponse(200, html)
        )

        result = lookup_handelsregister("Test GmbH")

        assert result == {"status": status, "source": "handelsregister"}

    def test_lookup_handelsregister_returns_none_without_matches(self, monkeypatch):
        _install_client(
            monkeypatch,
            "handelsregister",
            lambda *_args: FakeResponse(
                200, "<html><body>Nichts Relevantes</body></html>"
            ),
        )

        assert lookup_handelsregister("Test GmbH") is None

    @pytest.mark.parametrize("status_code", [400, 403])
    def test_lookup_handelsregister_disables_source_on_blocked_status(
        self, monkeypatch, status_code
    ):
        _install_client(
            monkeypatch,
            "handelsregister",
            lambda *_args: FakeResponse(status_code, "blocked"),
        )

        assert lookup_handelsregister("Test GmbH") is None
        assert is_source_disabled("handelsregister")

    def test_lookup_handelsregister_returns_none_when_client_raises(self, monkeypatch):
        def handler(*_args):
            raise httpx.ConnectError("reset")

        _install_client(monkeypatch, "handelsregister", handler)

        assert lookup_handelsregister("Test GmbH") is None


class TestWebsiteLookup:
    def test_build_company_slug_falls_back_when_name_has_no_word_characters(self):
        assert _build_company_slug("!!! GmbH") == "-gmbh"

    def test_lookup_website_returns_none_when_dns_fails(self, monkeypatch):
        monkeypatch.setattr(
            "biradar.sources.enrichment.website._dns_resolves", lambda _host: False
        )
        client = _install_client(
            monkeypatch,
            "website",
            lambda *_args: pytest.fail("client must not be called without DNS"),
        )

        assert lookup_website("Test GmbH") is None
        assert client.calls == []

    def test_lookup_website_parses_title_description_and_tech_signals(
        self, monkeypatch
    ):
        html = """<html><head>
            <title>Test GmbH - Startseite</title>
            <meta name="description" content="Innovative Tests aus Berlin">
            <script src="jquery.min.js"></script>
            </head>
            <body>
              <div id="__NEXT_DATA__">next</div>
              <p>Wir setzen Docker ein. Theme: wp-content.</p>
            </body></html>"""
        monkeypatch.setattr(
            "biradar.sources.enrichment.website._dns_resolves",
            lambda host: host.endswith(".de"),
        )
        _install_client(monkeypatch, "website", lambda *_args: FakeResponse(200, html))

        result = lookup_website("Test GmbH")

        assert result is not None
        assert result["url"] == "https://test.de"
        assert result["title"] == "Test GmbH - Startseite"
        assert result["description"] == "Innovative Tests aus Berlin"
        assert result["tech_signals"] == ["Next.js", "WordPress", "jQuery", "Docker"]
        assert result["status_code"] == 200
        assert result["source"] == "website"

    def test_lookup_website_parses_meta_description_with_reversed_attributes(
        self, monkeypatch
    ):
        html = (
            "<html><head><title>Anders</title>"
            '<meta content="Beschreibung hinter content" name="description">'
            "</head><body></body></html>"
        )
        monkeypatch.setattr(
            "biradar.sources.enrichment.website._dns_resolves",
            lambda host: host.endswith(".de"),
        )
        _install_client(monkeypatch, "website", lambda *_args: FakeResponse(200, html))

        result = lookup_website("Test GmbH")

        assert result is not None
        assert result["description"] == "Beschreibung hinter content"

    def test_lookup_website_skips_cloudflare_block_and_uses_next_candidate(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "biradar.sources.enrichment.website._dns_resolves",
            lambda host: host in ("test.de", "test.com"),
        )

        def handler(url, _params, _headers, _timeout):
            if url == "https://test.de":
                return FakeResponse(
                    403, "<html>Checking your browser... cloudflare</html>"
                )
            if url == "https://test.com":
                return FakeResponse(200, "<html><title>Fallback</title></html>")
            raise AssertionError(f"Unexpected URL: {url}")

        _install_client(monkeypatch, "website", handler)

        result = lookup_website("Test GmbH")

        assert result is not None
        assert result["url"] == "https://test.com"

    def test_lookup_website_skips_http_status_error(self, monkeypatch):
        monkeypatch.setattr(
            "biradar.sources.enrichment.website._dns_resolves",
            lambda host: host.endswith(".de"),
        )
        _install_client(
            monkeypatch, "website", lambda *_args: FakeResponse(500, "boom")
        )

        assert lookup_website("Test GmbH") is None

    def test_lookup_website_skips_connect_error(self, monkeypatch):
        monkeypatch.setattr(
            "biradar.sources.enrichment.website._dns_resolves",
            lambda host: host.endswith(".de"),
        )

        def handler(*_args):
            raise httpx.ConnectError("refused")

        _install_client(monkeypatch, "website", handler)

        assert lookup_website("Test GmbH") is None

    def test_lookup_website_skips_timeout(self, monkeypatch):
        monkeypatch.setattr(
            "biradar.sources.enrichment.website._dns_resolves",
            lambda host: host.endswith(".de"),
        )

        def handler(*_args):
            raise httpx.TimeoutException("too slow")

        _install_client(monkeypatch, "website", handler)

        assert lookup_website("Test GmbH") is None

    def test_lookup_website_skips_generic_request_error(self, monkeypatch):
        monkeypatch.setattr(
            "biradar.sources.enrichment.website._dns_resolves",
            lambda host: host.endswith(".de"),
        )

        def handler(*_args):
            raise httpx.TooManyRedirects("loop")

        _install_client(monkeypatch, "website", handler)

        assert lookup_website("Test GmbH") is None

    def test_lookup_website_skips_unreadable_response_body(self, monkeypatch):
        monkeypatch.setattr(
            "biradar.sources.enrichment.website._dns_resolves",
            lambda host: host.endswith(".de"),
        )
        _install_client(monkeypatch, "website", lambda *_args: BrokenTextResponse(200))

        assert lookup_website("Test GmbH") is None


class TestRuntimeClient:
    def test_get_source_config_returns_default_for_unknown_source(self):
        config = _get_source_config("does_not_exist_source")

        assert config.enabled is True
        assert config.timeout_seconds is None

    def test_get_client_is_lazy_singleton_and_close_resets_it(self):
        enrichment_runtime._close_client()
        try:
            client = enrichment_runtime._get_client()
            assert isinstance(client, httpx.Client)
            assert enrichment_runtime._get_client() is client
        finally:
            enrichment_runtime._close_client()

        assert enrichment_runtime._http_client is None


class TestHttpGet:
    def _patch(self, monkeypatch, handler):
        sleeps: list[float] = []
        _install_client(monkeypatch, "runtime", handler)
        monkeypatch.setattr(
            "biradar.sources.enrichment.runtime.time.sleep",
            lambda seconds: sleeps.append(seconds),
        )
        return sleeps

    def test_http_get_returns_none_after_three_timeouts(self, monkeypatch):
        calls = {"count": 0}

        def handler(*_args):
            calls["count"] += 1
            raise httpx.TimeoutException("too slow")

        sleeps = self._patch(monkeypatch, handler)

        assert _http_get("https://example.com") is None
        assert calls["count"] == 3
        assert sleeps == [1.0, 1.0]

    def test_http_get_returns_response_on_success(self, monkeypatch):
        response = FakeResponse(200, "<html>ok</html>")
        sleeps = self._patch(monkeypatch, lambda *_args: response)

        assert _http_get("https://example.com") is response
        assert sleeps == []

    def test_http_get_returns_none_on_cloudflare_block(self, monkeypatch):
        blocked = FakeResponse(403, "Access denied — cloudflare challenge page")
        sleeps = self._patch(monkeypatch, lambda *_args: blocked)

        assert _http_get("https://example.com") is None
        assert sleeps == []

    def test_http_get_returns_none_on_plain_403_without_retry(self, monkeypatch):
        forbidden = FakeResponse(403, "forbidden")
        sleeps = self._patch(monkeypatch, lambda *_args: forbidden)

        assert _http_get("https://example.com") is None
        assert sleeps == []

    def test_http_get_retries_server_errors_until_success(self, monkeypatch):
        responses = iter(
            [
                FakeResponse(500, "boom"),
                FakeResponse(500, "boom"),
                FakeResponse(200, "<html>fine</html>"),
            ]
        )
        sleeps = self._patch(monkeypatch, lambda *_args: next(responses))

        result = _http_get("https://example.com")

        assert result is not None
        assert result.status_code == 200
        assert sleeps == [1.0, 1.0]

    def test_http_get_returns_none_on_ssl_error_without_retry(self, monkeypatch):
        calls = {"count": 0}

        def handler(*_args):
            calls["count"] += 1
            raise ssl.SSLError("certificate verify failed")

        sleeps = self._patch(monkeypatch, handler)

        assert _http_get("https://example.com") is None
        assert calls["count"] == 1
        assert sleeps == []

    def test_http_get_returns_none_on_connect_error_without_retry(self, monkeypatch):
        calls = {"count": 0}

        def handler(*_args):
            calls["count"] += 1
            raise httpx.ConnectError("refused")

        sleeps = self._patch(monkeypatch, handler)

        assert _http_get("https://example.com") is None
        assert calls["count"] == 1
        assert sleeps == []

    def test_http_get_retries_generic_request_errors(self, monkeypatch):
        calls = {"count": 0}

        def handler(*_args):
            calls["count"] += 1
            raise httpx.ReadError("connection reset")

        sleeps = self._patch(monkeypatch, handler)

        assert _http_get("https://example.com") is None
        assert calls["count"] == 3
        assert sleeps == [1.0, 1.0]


class TestRuntimeSourceConfig:
    def test_source_timeout_seconds_uses_configured_source_value(self):
        assert source_timeout_seconds("handelsregister") == 5.0

    def test_source_timeout_seconds_falls_back_to_global_timeout(self):
        assert source_timeout_seconds("unknown_source_xyz") == 10.0

    def test_source_delay_seconds_falls_back_to_global_delay(self):
        assert source_delay_seconds("handelsregister") == 0.3


class TestUnternehmensregisterHelpers:
    def test_infer_legal_form_returns_none_for_plain_name(self):
        assert _infer_legal_form("Plain Name") is None

    def test_extract_balanced_json_array_survives_escaped_characters(self):
        text = 'x=["a\\"b", "c\\\\d", "[nested]"] trailing'
        start = text.index("[")

        extracted = _extract_balanced_json_array(text, start)

        assert extracted is not None
        assert json.loads(extracted) == ['a"b', "c\\d", "[nested]"]

    def test_extract_balanced_json_array_returns_none_without_closing_bracket(self):
        assert _extract_balanced_json_array('["a", "b" tail', 0) is None

    def test_extract_register_companies_skips_unparseable_company_arrays(self):
        html = '<div>{"companies":[{broken}]}</div>'

        assert _extract_register_companies(html) == []

    def test_select_best_company_returns_none_without_candidates(self):
        assert _select_best_company([], "Test GmbH") is None

    def test_select_best_company_matches_normalized_name(self):
        companies = [{"name": "Other GmbH"}, {"name": "Zalando  SE"}]

        assert _select_best_company(companies, "Zalando SE") is companies[1]

    def test_select_best_company_falls_back_to_first_candidate(self):
        companies = [{"name": "Other GmbH"}, {"name": "Zalando SE"}]

        assert _select_best_company(companies, "Nothing AG") is companies[0]

    def test_format_registry_number_requires_register_number(self):
        assert _format_registry_number({"registerType": {"name": "HRB"}}) is None

    def test_format_registry_number_combines_type_and_number(self):
        company = {"registerNumber": "158855", "registerType": {"name": "HRB"}}

        assert _format_registry_number(company) == "HRB 158855"

    def test_format_registry_number_handles_non_dict_register_type(self):
        assert (
            _format_registry_number({"registerNumber": 158855, "registerType": "HRB"})
            == "158855"
        )
        assert (
            _format_registry_number(
                {"registerNumber": "1", "registerType": {"other": "x"}}
            )
            == "1"
        )

    def test_format_registry_court_requires_dict_with_name(self):
        assert _format_registry_court({}) is None
        assert _format_registry_court({"registerCourt": "Berlin"}) is None
        assert _format_registry_court({"registerCourt": {"city": "Berlin"}}) is None

    def test_format_registry_court_prefixes_amtsgericht(self):
        company = {"registerCourt": {"name": "Berlin (Charlottenburg)"}}

        assert _format_registry_court(company) == (
            "Amtsgericht Berlin (Charlottenburg)"
        )

    def test_format_company_status_flags(self):
        assert _format_company_status({"deletedFlag": True}) == "deleted"
        assert _format_company_status({"deletedFlag": True, "changeFlag": True}) == (
            "deleted"
        )
        assert _format_company_status({"changeFlag": True}) == "changed"
        assert _format_company_status({}) == "active"


class TestUnternehmensregisterLookup:
    @pytest.mark.parametrize("status_code", [400, 403, 423, 451])
    def test_lookup_unternehmensregister_disables_source_on_blocked_token_status(
        self, monkeypatch, status_code
    ):
        _install_client(
            monkeypatch,
            "unternehmensregister",
            lambda *_args: FakeResponse(status_code, "denied"),
        )

        assert lookup_unternehmensregister("Test GmbH") is None
        assert is_source_disabled("unternehmensregister")

    @pytest.mark.parametrize("payload", [{"status": "ok"}, {"token": ""}, {"token": 5}])
    def test_lookup_unternehmensregister_returns_none_when_token_missing(
        self, monkeypatch, payload
    ):
        _install_client(
            monkeypatch,
            "unternehmensregister",
            lambda *_args: FakeResponse(200, payload=payload),
        )

        assert lookup_unternehmensregister("Test GmbH") is None
        assert not is_source_disabled("unternehmensregister")

    def test_lookup_unternehmensregister_disables_source_on_blocked_search(
        self, monkeypatch
    ):
        token_response = FakeResponse(200, payload={"token": "secret"})
        search_response = FakeResponse(423, "locked")

        def handler(url, _params, _headers, _timeout):
            if url.endswith("/api/search-token"):
                return token_response
            return search_response

        _install_client(monkeypatch, "unternehmensregister", handler)

        assert lookup_unternehmensregister("Test GmbH") is None
        assert is_source_disabled("unternehmensregister")

    def test_lookup_unternehmensregister_returns_none_without_companies_payload(
        self, monkeypatch
    ):
        token_response = FakeResponse(200, payload={"token": "secret"})

        def handler(url, _params, _headers, _timeout):
            if url.endswith("/api/search-token"):
                return token_response
            return FakeResponse(200, "<html><body>Keine Treffer</body></html>")

        _install_client(monkeypatch, "unternehmensregister", handler)

        assert lookup_unternehmensregister("Test GmbH") is None

    def test_lookup_unternehmensregister_returns_none_when_client_raises(
        self, monkeypatch
    ):
        def handler(*_args):
            raise httpx.ConnectError("refused")

        _install_client(monkeypatch, "unternehmensregister", handler)

        assert lookup_unternehmensregister("Test GmbH") is None


class TestResolveEnrichmentSources:
    def test_resolve_enrichment_sources_excludes_config_disabled_sources(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "biradar.sources.enrichment.orchestrator._get_enrichment_config",
            lambda: SimpleNamespace(
                enabled=True,
                delay_between_sources=0.0,
                sources={
                    "github": SimpleNamespace(enabled=False),
                    "website": SimpleNamespace(enabled=True),
                    "north_data": True,
                },
            ),
        )

        resolved = _resolve_enrichment_sources()

        names = [source.name for source in resolved]
        assert "github" not in names
        assert "website" in names
        assert "north_data" in names
        assert "bundesanzeiger" in names
        assert get_registered_enrichment_sources()


class TestAggregateResultHandelsregisterAndReports:
    def test_aggregate_result_merges_handelsregister_fields(self):
        result = _aggregate_result(
            [
                {
                    "source": "handelsregister",
                    "legal_form": "GmbH",
                    "registry_court": "Amtsgericht Berlin",
                    "registry_number": "HRB 1",
                    "status": "active",
                }
            ]
        )

        assert result["legal_form"] == "GmbH"
        assert result["sector"] == "Legal form: GmbH"
        assert result["registry_court"] == "Amtsgericht Berlin"
        assert result["registry_number"] == "HRB 1"
        assert result["company_status"] == "active"

    def test_aggregate_result_falls_back_to_reports_for_funding_info(self):
        result = _aggregate_result(
            [
                {
                    "source": "bundesanzeiger",
                    "revenue_estimate": None,
                    "annual_reports": ["Jahresabschluss 2024", "Jahresabschluss 2025"],
                }
            ]
        )

        assert result["funding_info"] == (
            "Reports: Jahresabschluss 2024, Jahresabschluss 2025"
        )


class TestEnrichCandidateDisabledSource:
    def test_enrich_candidate_skips_source_disabled_after_terminal_error(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "biradar.sources.enrichment.orchestrator._get_enrichment_config",
            lambda: SimpleNamespace(
                enabled=True, delay_between_sources=0.0, sources={}
            ),
        )
        monkeypatch.setattr(
            "biradar.sources.enrichment.orchestrator._resolve_enrichment_sources",
            lambda: [
                EnrichmentSourceDefinition(
                    "bundesanzeiger", lambda _company_name: {"source": "bundesanzeiger"}
                )
            ],
        )
        disable_source("bundesanzeiger")

        result = enrich_candidate("Test GmbH")

        assert (
            "bundesanzeiger: skipped (disabled after terminal error)" in result.errors
        )
        assert result.enriched is False
        assert result.sources == []


class TestNorthDataLookup:
    def test_lookup_north_data_applies_link_filters_and_follows_detail_link(
        self, monkeypatch
    ):
        search_html = """<html><body>
            <a href="/_next/static/chunk.js">bundle</a>
            <a href="/root-level">Root</a>
            <a href="https://external.example.com/page">External</a>
            <a href="/Example%20GmbH,%20Berlin/Amtsgericht%20Berlin%20HRB%2012345">
                Example GmbH
            </a>
        </body></html>"""
        detail_html = """<html>
          <head>
            <title>Example GmbH, Berlin, Amtsgericht Berlin HRB 12345: Stammdaten</title>
          </head>
          <body>
            <script type="application/ld+json">
              {"@type":"BreadcrumbList","itemListElement":[
                {"item":{"name":"Firmen"}},
                {"item":{"name":"Software development"}}
              ]}
            </script>
          </body>
        </html>"""

        def handler(url, params, _headers, _timeout):
            if params is not None and params.get("query") == "Example GmbH":
                return FakeResponse(200, search_html)
            if url.endswith("HRB%2012345"):
                return FakeResponse(200, detail_html)
            raise AssertionError(f"Unexpected URL: {url}")

        client = _install_client(monkeypatch, "north_data", handler)

        result = lookup_north_data("Example GmbH")

        assert len(client.calls) == 2
        assert result is not None
        assert result["registry_number"] == "HRB 12345"
        assert result["sector"] == "Software development"
        assert result["source"] == "north_data"
        assert result["source_url"] == (
            "https://www.northdata.de/Example%20GmbH,%20Berlin/"
            "Amtsgericht%20Berlin%20HRB%2012345"
        )

    def test_lookup_north_data_skips_links_without_string_href(self, monkeypatch):
        monkeypatch.setattr(
            "biradar.sources.enrichment.north_data.attr_str",
            lambda *_args, **_kwargs: None,
        )
        search_html = (
            "<html><body>"
            '<a href="/Example%20GmbH/Amtsgericht%20Berlin%20HRB%2012345">Example</a>'
            "</body></html>"
        )
        client = _install_client(
            monkeypatch, "north_data", lambda *_args: FakeResponse(200, search_html)
        )

        assert lookup_north_data("Example GmbH") is None
        assert len(client.calls) == 1

    def test_lookup_north_data_returns_none_without_valid_links(self, monkeypatch):
        search_html = """<html><body>
            <a href="/_next/static/chunk.js">bundle</a>
            <a href="/root-level">Root</a>
        </body></html>"""
        client = _install_client(
            monkeypatch, "north_data", lambda *_args: FakeResponse(200, search_html)
        )

        assert lookup_north_data("Example GmbH") is None
        assert len(client.calls) == 1

    def test_lookup_north_data_returns_registry_number_despite_broken_ldjson(
        self, monkeypatch
    ):
        search_html = (
            "<html><body>"
            '<a href="/Example%20GmbH/Amtsgericht%20Berlin%20HRB%2012345">Example</a>'
            "</body></html>"
        )
        detail_html = """<html>
          <head><title>Example GmbH, Amtsgericht Berlin HRB 12345: Netzwerk</title></head>
          <body>
            <script type="application/ld+json">{"broken"</script>
          </body>
        </html>"""

        def handler(url, params, _headers, _timeout):
            if params is not None:
                return FakeResponse(200, search_html)
            return FakeResponse(200, detail_html)

        _install_client(monkeypatch, "north_data", handler)

        result = lookup_north_data("Example GmbH")

        assert result is not None
        assert result["registry_number"] == "HRB 12345"
        assert result["sector"] is None

    def test_lookup_north_data_returns_none_without_registry_number_or_sector(
        self, monkeypatch
    ):
        search_html = (
            '<html><body><a href="/Example%20GmbH/Seite">Example</a></body></html>'
        )
        detail_html = """<html>
          <head><title>Example GmbH Homepage</title></head>
          <body>
            <script type="application/ld+json">{"@type":"WebPage"}</script>
          </body>
        </html>"""

        def handler(url, params, _headers, _timeout):
            if params is not None:
                return FakeResponse(200, search_html)
            return FakeResponse(200, detail_html)

        _install_client(monkeypatch, "north_data", handler)

        assert lookup_north_data("Example GmbH") is None

    def test_lookup_north_data_returns_none_when_client_raises(self, monkeypatch):
        def handler(*_args):
            raise httpx.ConnectError("refused")

        _install_client(monkeypatch, "north_data", handler)

        assert lookup_north_data("Example GmbH") is None


class TestWikidataLookup:
    def test_lookup_wikidata_returns_none_when_search_is_empty(self, monkeypatch):
        _install_client(
            monkeypatch,
            "wikidata",
            lambda *_args: FakeResponse(200, payload={"search": []}),
        )

        assert lookup_wikidata("Example GmbH") is None

    def test_lookup_wikidata_returns_none_when_hit_has_no_id(self, monkeypatch):
        _install_client(
            monkeypatch,
            "wikidata",
            lambda *_args: FakeResponse(200, payload={"search": [{"label": "x"}]}),
        )

        assert lookup_wikidata("Example GmbH") is None

    def test_lookup_wikidata_returns_none_without_relevant_claims(self, monkeypatch):
        def handler(_url, params, _headers, _timeout):
            if params["action"] == "wbsearchentities":
                return FakeResponse(200, payload={"search": [{"id": "Q1"}]})
            if params["action"] == "wbgetentities":
                return FakeResponse(
                    200,
                    payload={"entities": {"Q1": {"claims": {"P571": []}}}},
                )
            raise AssertionError(f"Unexpected params: {params}")

        _install_client(monkeypatch, "wikidata", handler)

        assert lookup_wikidata("Example GmbH") is None

    def test_lookup_wikidata_returns_none_when_client_raises(self, monkeypatch):
        def handler(*_args):
            raise httpx.ConnectError("refused")

        _install_client(monkeypatch, "wikidata", handler)

        assert lookup_wikidata("Example GmbH") is None


class TestRegistryState:
    def test_disable_source_marks_source_until_reset(self):
        disable_source("temp_source")

        assert is_source_disabled("temp_source") is True

        _reset_disabled_sources()

        assert is_source_disabled("temp_source") is False

    def test_registered_enrichment_sources_populated_on_import(self):
        names = {source.name for source in get_registered_enrichment_sources()}

        assert {
            "bundesanzeiger",
            "github",
            "handelsregister",
            "north_data",
            "unternehmensregister",
            "website",
            "wikidata",
        } <= names
        assert is_source_disabled("bundesanzeiger") is False
