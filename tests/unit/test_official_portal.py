"""Unit tests for official portal source adapter parsing."""

from datetime import date
from pathlib import Path

import httpx
import pytest

from biradar.sources.official_portal import (
    JSFSession,
    OfficialPortalAdapter,
    _infer_legal_form,
    _normalize_publication_date,
)
from biradar.storage.db import Database

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "official_portal"

FORM_PAGE_HTML = (
    '<form id="frm_suche" action="/ap/suche.jsf">'
    '<input name="jakarta.faces.ViewState" value="state123" />'
    "</form>"
)
SEARCH_FORM_WITHOUT_RESULTS_HTML = (
    "<!DOCTYPE html><html><body>" + FORM_PAGE_HTML + "</body></html>"
)
RESULTS_PAGE_HTML = (FIXTURE_DIR / "sample_response.html").read_text(encoding="utf-8")


class FakePortalResponse:
    """Minimal async response stub for portal fetch tests."""

    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request(
                "POST", "https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf"
            )
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=request, response=self
            )


class FakeAsyncClient:
    """Async client stub serving canned GET/POST responses in order.

    The last entry of ``post_responses`` repeats once the list is exhausted;
    entries may be exceptions to raise instead of responses to return.
    """

    def __init__(self, post_responses=None, get_response=None):
        self.post_responses = list(post_responses or [])
        self.get_response = get_response
        self.post_attempts = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        if isinstance(self.get_response, Exception):
            raise self.get_response
        return self.get_response or FakePortalResponse(200, FORM_PAGE_HTML)

    async def post(self, *args, **kwargs):
        self.post_attempts += 1
        index = min(self.post_attempts - 1, len(self.post_responses) - 1)
        item = self.post_responses[index] if self.post_responses else None
        if isinstance(item, Exception):
            raise item
        return item


def test_parse_html_response_extracts_table_data():
    """Test that the HTML results parser correctly extracts rows from the live portal format."""
    html_fixture = (FIXTURE_DIR / "sample_response.html").read_text(encoding="utf-8")
    adapter = OfficialPortalAdapter(db=None)

    records = adapter._parse_response(html_fixture)

    assert len(records) == 1
    record = records[0]
    assert record["company_name"] == "Test Berlin GmbH"
    assert record["legal_form"] == "GmbH"
    assert record["court"] == "Amtsgericht Charlottenburg (Berlin)"
    assert record["case_number"] == "36e IN 123/26"
    assert record["publication_date"] == "2026-06-15"
    assert record["register_number"] == "Berlin, HRB 123456"


def test_parse_response_extracts_jsf_table_data():
    """Test that the JSF XML response parser correctly extracts table rows."""
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <partial-response>
        <changes>
            <update id="form:resultsTable">
                <![CDATA[
                <table id="form:resultsTable">
                    <tbody>
                        <tr>
                            <td>15.06.2026</td>
                            <td>36e IN 123/26</td>
                            <td>Amtsgericht Charlottenburg</td>
                            <td>Test Berlin GmbH</td>
                            <td>Berlin</td>
                            <td>Berlin, HRB 123456</td>
                        </tr>
                    </tbody>
                </table>
                ]]>
            </update>
        </changes>
    </partial-response>
    """

    adapter = OfficialPortalAdapter(db=None)  # db not needed for parsing
    records = adapter._parse_response(mock_xml)

    assert len(records) == 1
    record = records[0]
    assert record["company_name"] == "Test Berlin GmbH"
    assert record["legal_form"] == "GmbH"
    assert record["court"] == "Amtsgericht Charlottenburg"
    assert record["case_number"] == "36e IN 123/26"
    assert record["publication_date"] == "2026-06-15"
    assert record["register_number"] == "Berlin, HRB 123456"
    assert "Test Berlin GmbH" in record["raw_text"]


def test_parse_response_handles_empty_or_malformed_xml():
    """Test that the parser safely handles malformed XML without crashing."""
    adapter = OfficialPortalAdapter(db=None)

    # Malformed XML
    records1 = adapter._parse_response("<broken><xml>")
    assert records1 == []

    # Empty string
    records2 = adapter._parse_response("")
    assert records2 == []

    # Valid XML but no table
    records3 = adapter._parse_response(
        '<?xml version="1.0"?><partial-response><update id="other">No table here</update></partial-response>'
    )
    assert records3 == []


def test_parse_response_handles_leading_comments_before_xml_declaration():
    """JSF fixtures may contain leading HTML comments before the XML declaration."""
    adapter = OfficialPortalAdapter(db=None)
    xml_with_comment = """<!-- fixture comment -->
<?xml version="1.0" encoding="UTF-8"?>
<partial-response>
  <changes>
    <update id="form:results">
      <![CDATA[
      <table><tbody><tr><td>16.06.2026</td><td>1 IN 1/26</td><td>Berlin</td><td>Alpha UG</td><td>Berlin</td><td></td></tr></tbody></table>
      ]]>
    </update>
  </changes>
</partial-response>
"""
    records = adapter._parse_response(xml_with_comment)
    assert len(records) == 1
    assert records[0]["company_name"] == "Alpha UG"


def test_parse_response_extracts_span_based_live_layout():
    adapter = OfficialPortalAdapter(db=None)
    html = """<!DOCTYPE html>
<html>
  <body>
    <h1>Suchergebnis</h1>
    <div id="tbl_ergebnis:0:otx_datum">19.06.2026</div>
    <div id="tbl_ergebnis:0:otx_aktenzeichen">12 IN 99/26</div>
    <div id="tbl_ergebnis:0:otx_gericht">Amtsgericht Charlottenburg</div>
    <div id="tbl_ergebnis:0:otx_schuldner">Modern Berlin GmbH</div>
    <div id="tbl_ergebnis:0:otx_registereintrag">Berlin, HRB 999999</div>
  </body>
</html>
"""
    records = adapter._parse_response(html)

    assert len(records) == 1
    record = records[0]
    assert record["company_name"] == "Modern Berlin GmbH"
    assert record["court"] == "Amtsgericht Charlottenburg"
    assert record["case_number"] == "12 IN 99/26"
    assert record["publication_date"] == "2026-06-19"
    assert record["register_number"] == "Berlin, HRB 999999"


def test_parse_response_classifies_too_many_results_page():
    adapter = OfficialPortalAdapter(db=None)
    html = """<!DOCTYPE html>
<html>
  <body>
    <h1>Suchergebnis</h1>
    <table><tr><td>Ihre Suche ergab zu viele Treffer. Die maximale Trefferzahl beträgt 1000.</td></tr></table>
  </body>
</html>
"""
    parsed = adapter._parse_response_details(html)

    assert parsed.records == []
    assert parsed.error_code == "too_many_results"


@pytest.mark.anyio
async def test_fetch_date_range_stops_retry_on_anti_bot(monkeypatch):
    attempts = {"post": 0}

    async def fake_sleep(*args, **kwargs):
        return None

    class FakeResponse:
        def __init__(self, status_code: int, text: str):
            self.status_code = status_code
            self.text = text

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError("should not be called for anti-bot branch")

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse(
                200,
                '<form id="frm_suche" action="/ap/suche.jsf">'
                '<input name="jakarta.faces.ViewState" value="state123" />'
                "</form>",
            )

        async def post(self, *args, **kwargs):
            attempts["post"] += 1
            return FakeResponse(403, "cloudflare blocked")

    monkeypatch.setattr(
        "biradar.sources.official_portal.httpx.AsyncClient", FakeAsyncClient
    )
    monkeypatch.setattr("biradar.sources.official_portal.asyncio.sleep", fake_sleep)

    adapter = OfficialPortalAdapter(db=None)
    result = await adapter.fetch_date_range(
        start_date=date(2026, 6, 10),
        end_date=date(2026, 6, 16),
        dry_run=True,
    )
    assert result["status"] == "failed"
    assert result["errors"] == ["blocked_by_anti_bot"]
    assert attempts["post"] == 1


def test_infer_legal_form_returns_none_for_plain_name():
    assert _infer_legal_form("Berliner Rathaus") is None


def test_normalize_publication_date_keeps_unparseable_value():
    assert _normalize_publication_date("2026-06-15") == "2026-06-15"


def test_parse_html_table_skips_rows_with_missing_columns():
    adapter = OfficialPortalAdapter(db=None)
    html = """<!DOCTYPE html>
<html>
  <body>
    <table id="tbl_ergebnis">
      <tbody>
        <tr><td>15.06.2026</td><td>36e IN 1/26</td></tr>
        <tr>
          <td>15.06.2026</td>
          <td>36e IN 2/26</td>
          <td>Amtsgericht Charlottenburg</td>
          <td>Test Berlin GmbH</td>
          <td>Berlin</td>
          <td>Berlin, HRB 123456</td>
          <td></td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""
    records = adapter._parse_response(html)

    assert len(records) == 1
    assert records[0]["case_number"] == "36e IN 2/26"


def test_parse_html_returns_clean_empty_response_without_tables():
    adapter = OfficialPortalAdapter(db=None)

    parsed = adapter._parse_response_details(
        "<!DOCTYPE html><html><body><p>Keine Daten</p></body></html>"
    )

    assert parsed.records == []
    assert parsed.parser_name == "html_results_parser"
    assert parsed.error_code is None


def test_parse_html_reports_parser_mismatch_for_empty_results_page():
    adapter = OfficialPortalAdapter(db=None)

    parsed = adapter._parse_response_details(
        "<!DOCTYPE html><html><body><h1>Suchergebnis</h1></body></html>"
    )

    assert parsed.records == []
    assert parsed.parser_name == "html_results_parser"
    assert parsed.error_code == "parser_mismatch"


def test_parse_html_flags_search_form_page_without_results():
    adapter = OfficialPortalAdapter(db=None)

    parsed = adapter._parse_response_details(SEARCH_FORM_WITHOUT_RESULTS_HTML)

    assert parsed.records == []
    assert parsed.parser_name == "portal_error_parser"
    assert parsed.error_code == "search_form_returned_without_results"


def test_parse_span_layout_skips_empty_field_names_and_partial_rows():
    adapter = OfficialPortalAdapter(db=None)
    html = """<!DOCTYPE html>
<html>
  <body>
    <h1>Suchergebnis</h1>
    <div id="tbl_ergebnis:0:otx_"></div>
    <div id="tbl_ergebnis:0:otx_datum">19.06.2026</div>
    <div id="tbl_ergebnis:1:otx_datum">20.06.2026</div>
    <div id="tbl_ergebnis:1:otx_aktenzeichen">13 IN 5/26</div>
    <div id="tbl_ergebnis:1:otx_gericht">Amtsgericht Mitte</div>
    <div id="tbl_ergebnis:1:otx_schuldner">Zweit GmbH</div>
  </body>
</html>
"""
    records = adapter._parse_response(html)

    assert len(records) == 1
    assert records[0]["company_name"] == "Zweit GmbH"
    assert records[0]["case_number"] == "13 IN 5/26"
    assert records[0]["publication_date"] == "2026-06-20"


def test_parse_jsf_skips_updates_without_content():
    adapter = OfficialPortalAdapter(db=None)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<partial-response><changes>"
        '<update id="form:results"></update>'
        "</changes></partial-response>"
    )

    parsed = adapter._parse_response_details(xml)

    assert parsed.records == []
    assert parsed.parser_name == "jsf_partial_parser"
    assert parsed.error_code is None


def test_parse_jsf_propagates_error_from_update_payload():
    adapter = OfficialPortalAdapter(db=None)
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<partial-response>
  <changes>
    <update id="form:resultsTable"><![CDATA[
      <div>Ihre Suche ergab zu viele Treffer. Die maximale Trefferzahl beträgt 500.</div>
    ]]></update>
  </changes>
</partial-response>
"""

    parsed = adapter._parse_response_details(xml)

    assert parsed.records == []
    assert parsed.parser_name == "portal_error_parser"
    assert parsed.error_code == "too_many_results"


def test_parse_response_details_maps_internal_parser_errors_to_mismatch():
    adapter = OfficialPortalAdapter(db=None)

    # None is not a valid response body; the parser must classify it safely.
    parsed = adapter._parse_response_details(None)

    assert parsed.records == []
    assert parsed.parser_name == "unknown_parser"
    assert parsed.error_code == "parser_mismatch"


def test_fetch_fixture_date_range_records_failure_for_missing_fixture(tmp_path):
    adapter = OfficialPortalAdapter(db=None)

    result = adapter.fetch_fixture_date_range(
        fixture_path=str(tmp_path / "missing.html"),
        start_date=date(2026, 6, 10),
        end_date=date(2026, 6, 16),
        dry_run=True,
    )

    assert result["status"] == "failed"
    assert result["records_seen"] == 0
    assert result["records_imported"] == 0
    assert len(result["errors"]) == 1


@pytest.mark.anyio
async def test_jsf_session_initialize_raises_without_search_form():
    class NoFormClient:
        async def get(self, *args, **kwargs):
            return FakePortalResponse(
                200, "<html><body><p>Kein Formular</p></body></html>"
            )

    session = JSFSession(NoFormClient())

    with pytest.raises(RuntimeError, match="frm_suche"):
        await session.initialize()


@pytest.mark.anyio
async def test_jsf_session_initialize_raises_without_view_state():
    class NoViewStateClient:
        async def get(self, *args, **kwargs):
            return FakePortalResponse(
                200, '<form id="frm_suche" action="/ap/suche.jsf"></form>'
            )

    session = JSFSession(NoViewStateClient())

    with pytest.raises(RuntimeError, match="ViewState"):
        await session.initialize()


@pytest.mark.anyio
async def test_jsf_session_initialize_extracts_state_and_token():
    class StatefulClient:
        async def get(self, *args, **kwargs):
            return FakePortalResponse(
                200,
                FORM_PAGE_HTML + '<input type="hidden" name="token" value="csrf456" />',
            )

    session = JSFSession(StatefulClient())
    await session.initialize()

    assert session.view_state == "state123"
    csrf_value = session.token
    assert csrf_value == "csrf456"
    assert session.form_action == (
        "https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf"
    )

    payload = session.get_payload({"frm_suche:cbt_suchen": "Suchen"})

    assert payload == {
        "frm_suche": "frm_suche",
        "jakarta.faces.ViewState": "state123",
        "token": "csrf456",
        "frm_suche:cbt_suchen": "Suchen",
    }


@pytest.mark.anyio
async def test_fetch_date_range_persists_records_and_completes_run(
    tmp_path, monkeypatch
):
    async def fake_sleep(delay=None):
        return None

    client = FakeAsyncClient(
        post_responses=[FakePortalResponse(200, RESULTS_PAGE_HTML)]
    )
    monkeypatch.setattr(
        "biradar.sources.official_portal.httpx.AsyncClient",
        lambda *_args, **_kwargs: client,
    )
    monkeypatch.setattr("biradar.sources.official_portal.asyncio.sleep", fake_sleep)

    db = Database(tmp_path / "portal.duckdb")
    try:
        db.run_migrations()
        adapter = OfficialPortalAdapter(db=db)
        result = await adapter.fetch_date_range(
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 16),
            dry_run=False,
        )

        assert result["status"] == "completed"
        assert result["records_seen"] == 1
        assert result["records_imported"] == 1
        assert result["records"][0]["raw_record_id"].startswith("raw_")

        runs = db.conn.execute(
            "SELECT status, records_seen, records_imported FROM source_runs"
        ).fetchall()
        assert runs == [("completed", 1, 1)]
    finally:
        db.close()


@pytest.mark.anyio
async def test_fetch_date_range_retries_after_post_timeout(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay=None):
        sleeps.append(delay)

    client = FakeAsyncClient(
        post_responses=[
            httpx.TimeoutException("timed out"),
            FakePortalResponse(200, RESULTS_PAGE_HTML),
        ]
    )
    monkeypatch.setattr(
        "biradar.sources.official_portal.httpx.AsyncClient",
        lambda *_args, **_kwargs: client,
    )
    monkeypatch.setattr("biradar.sources.official_portal.asyncio.sleep", fake_sleep)

    adapter = OfficialPortalAdapter(db=None)
    result = await adapter.fetch_date_range(
        start_date=date(2026, 6, 10),
        end_date=date(2026, 6, 16),
        dry_run=True,
    )

    assert client.post_attempts == 2
    assert sleeps == [1.5, 2.0]
    assert result["status"] == "completed"
    assert result["records_seen"] == 1


@pytest.mark.anyio
async def test_fetch_date_range_reports_http_status_error(monkeypatch):
    async def fake_sleep(delay=None):
        return None

    client = FakeAsyncClient(post_responses=[FakePortalResponse(500, "exploded")])
    monkeypatch.setattr(
        "biradar.sources.official_portal.httpx.AsyncClient",
        lambda *_args, **_kwargs: client,
    )
    monkeypatch.setattr("biradar.sources.official_portal.asyncio.sleep", fake_sleep)

    adapter = OfficialPortalAdapter(db=None)
    result = await adapter.fetch_date_range(
        start_date=date(2026, 6, 10),
        end_date=date(2026, 6, 16),
        dry_run=True,
    )

    assert client.post_attempts == 1
    assert result["status"] == "failed"
    assert result["errors"] == ["HTTP error 500"]


@pytest.mark.anyio
async def test_fetch_date_range_reports_unexpected_post_error(monkeypatch):
    async def fake_sleep(delay=None):
        return None

    client = FakeAsyncClient(post_responses=[RuntimeError("socket hung up")])
    monkeypatch.setattr(
        "biradar.sources.official_portal.httpx.AsyncClient",
        lambda *_args, **_kwargs: client,
    )
    monkeypatch.setattr("biradar.sources.official_portal.asyncio.sleep", fake_sleep)

    adapter = OfficialPortalAdapter(db=None)
    result = await adapter.fetch_date_range(
        start_date=date(2026, 6, 10),
        end_date=date(2026, 6, 16),
        dry_run=True,
    )

    assert result["status"] == "failed"
    assert result["errors"] == ["Unexpected error: socket hung up"]


@pytest.mark.anyio
async def test_fetch_date_range_reports_error_code_from_response_page(monkeypatch):
    async def fake_sleep(delay=None):
        return None

    client = FakeAsyncClient(
        post_responses=[FakePortalResponse(200, SEARCH_FORM_WITHOUT_RESULTS_HTML)]
    )
    monkeypatch.setattr(
        "biradar.sources.official_portal.httpx.AsyncClient",
        lambda *_args, **_kwargs: client,
    )
    monkeypatch.setattr("biradar.sources.official_portal.asyncio.sleep", fake_sleep)

    adapter = OfficialPortalAdapter(db=None)
    result = await adapter.fetch_date_range(
        start_date=date(2026, 6, 10),
        end_date=date(2026, 6, 16),
        dry_run=True,
    )

    assert client.post_attempts == 1
    assert result["status"] == "failed"
    assert result["errors"] == ["search_form_returned_without_results"]


@pytest.mark.anyio
async def test_fetch_date_range_reports_session_initialization_failure(monkeypatch):
    async def fake_sleep(delay=None):
        return None

    client = FakeAsyncClient(get_response=RuntimeError("dns gone"))
    monkeypatch.setattr(
        "biradar.sources.official_portal.httpx.AsyncClient",
        lambda *_args, **_kwargs: client,
    )
    monkeypatch.setattr("biradar.sources.official_portal.asyncio.sleep", fake_sleep)

    adapter = OfficialPortalAdapter(db=None)
    result = await adapter.fetch_date_range(
        start_date=date(2026, 6, 10),
        end_date=date(2026, 6, 16),
        dry_run=True,
    )

    assert result["status"] == "failed"
    assert result["errors"] == ["Session initialization failed: dns gone"]
