"""Unit tests for official portal source adapter parsing."""

from datetime import date

import pytest

from biradar.sources.official_portal import OfficialPortalAdapter


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
                            <td>Test Berlin GmbH</td>
                            <td>Amtsgericht Charlottenburg</td>
                            <td>36e IN 123/26</td>
                            <td>15.06.2026</td>
                            <td>Eröffnungsbeschluss</td>
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
    assert record["proceeding_stage"] == "Eröffnungsbeschluss"
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
      <table><tbody><tr><td>Alpha UG</td><td>Berlin</td><td>1 IN 1/26</td><td>16.06.2026</td><td>Beschluss</td></tr></tbody></table>
      ]]>
    </update>
  </changes>
</partial-response>
"""
    records = adapter._parse_response(xml_with_comment)
    assert len(records) == 1
    assert records[0]["company_name"] == "Alpha UG"


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
