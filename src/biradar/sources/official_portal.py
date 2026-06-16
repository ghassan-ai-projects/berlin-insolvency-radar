"""Official portal source adapter for neu.insolvenzbekanntmachungen.de.

This adapter implements JSF session management against the current live portal
markup, including extracting and replaying the active `jakarta.faces.ViewState`
and submitting the real `frm_suche` search form.
"""

import asyncio
import hashlib
import json
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from biradar.observability.logging import get_logger
from biradar.storage.repository import RawRecordRepository, SourceRunRepository

logger = get_logger(__name__)

PORTAL_URL = "https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _infer_legal_form(company_name: str) -> str | None:
    """Infer a corporate legal form from the company name."""
    normalized = company_name.upper()
    canonical_forms = {
        "GMBH & CO. KG": "GmbH & Co. KG",
        "GMBH & CO KG": "GmbH & Co KG",
        "GMBH": "GmbH",
        "UG": "UG",
        "AG": "AG",
        "KG": "KG",
        "OHG": "OHG",
        "EG": "eG",
        "SE": "SE",
        "LTD": "Ltd",
    }
    for legal_form, canonical in canonical_forms.items():
        if legal_form in normalized:
            return canonical
    return None


def _normalize_publication_date(value: str) -> str:
    """Normalize portal date strings to ISO format when possible."""
    try:
        return datetime.strptime(value, "%d.%m.%Y").date().isoformat()
    except ValueError:
        return value


class JSFSession:
    """Manages JSF session state, including ViewState and cookies."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.view_state: str | None = None
        self.token: str | None = None
        self.form_action: str = PORTAL_URL
        self.form_id: str = "frm_suche"
        self.view_state_field: str = "jakarta.faces.ViewState"

    async def initialize(self) -> None:
        """Initialize the session by fetching the initial page and extracting JSF state."""
        logger.info("Initializing JSF session for official portal")
        response = await self.client.get(PORTAL_URL, timeout=15.0)
        response.raise_for_status()

        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        search_form = soup.find("form", {"id": self.form_id})
        if search_form is None:
            raise RuntimeError("Search form frm_suche not found on official portal")

        action = search_form.get("action")
        if action:
            self.form_action = urljoin(PORTAL_URL, action)

        view_state_input = search_form.find("input", {"name": self.view_state_field})
        if view_state_input and view_state_input.get("value"):
            self.view_state = view_state_input.get("value")
            logger.debug("Extracted jakarta.faces.ViewState")
        else:
            raise RuntimeError("Could not extract jakarta.faces.ViewState")

        # Extract CSRF token if present (often named 'token' or similar in JSF)
        token_match = re.search(r'<input[^>]*name="token"[^>]*value="([^"]*)"', html)
        if token_match:
            self.token = token_match.group(1)
            logger.debug("Extracted CSRF token")

    def get_payload(self, form_data: dict[str, Any]) -> dict[str, Any]:
        """Build the JSF POST payload with required state fields."""
        payload = {
            self.form_id: self.form_id,
        }
        if self.view_state:
            payload[self.view_state_field] = self.view_state
        if self.token:
            payload["token"] = self.token
        payload.update(form_data)
        return payload


class OfficialPortalAdapter:
    """Adapter for fetching insolvency records from the official German portal."""

    def __init__(self, db):
        self.source_run_repo = SourceRunRepository(db)
        self.raw_record_repo = RawRecordRepository(db)
        self.source_id = "official_insolvency_portal"

    def _persist_records(
        self,
        source_run_id: str,
        records: list[dict[str, Any]],
        dry_run: bool,
    ) -> tuple[int, int]:
        """Persist parsed records and attach persisted raw-record IDs."""
        records_seen = len(records)
        records_imported = 0
        for record in records:
            raw_text = record.get("raw_text", "")
            content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            raw_record_id = f"raw_{uuid.uuid4().hex}"
            retrieved_at = datetime.now(UTC).isoformat()
            if not dry_run:
                persisted_raw_record_id = self.raw_record_repo.upsert_raw_record(
                    raw_record_id=raw_record_id,
                    source_run_id=source_run_id,
                    source_id=self.source_id,
                    external_id=record.get("external_id"),
                    retrieved_at=retrieved_at,
                    source_url=record.get("source_url"),
                    raw_text=raw_text,
                    raw_json=None,
                    content_hash=content_hash,
                    parser_version="v1",
                )
                record["raw_record_id"] = persisted_raw_record_id
            records_imported += 1
        return records_seen, records_imported

    def fetch_fixture_date_range(
        self,
        fixture_path: str,
        start_date: date,
        end_date: date,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Fetch records from a saved fixture while preserving source-run behavior."""
        source_run_id = str(uuid.uuid4())
        errors: list[str] = []
        records: list[dict[str, Any]] = []
        duplicates = 0
        rejected = 0

        if not dry_run:
            self.source_run_repo.create_run(
                source_run_id=source_run_id,
                source_id=self.source_id,
                run_type="fixture_scrape",
                params_json=f'{{"start_date": "{start_date.isoformat()}", "end_date": "{end_date.isoformat()}", "fixture_path": "{fixture_path}"}}',
            )

        try:
            html_or_xml = Path(fixture_path).read_text(encoding="utf-8")
            records = self._parse_response(html_or_xml)
            records_seen, records_imported = self._persist_records(
                source_run_id, records, dry_run
            )
        except Exception as exc:
            records_seen = 0
            records_imported = 0
            errors.append(str(exc))

        if not dry_run:
            self.source_run_repo.complete_run(
                source_run_id=source_run_id,
                records_seen=records_seen,
                records_imported=records_imported,
                duplicates=duplicates,
                rejected=rejected,
                error_json=json.dumps(errors) if errors else None,
            )

        return {
            "source_run_id": source_run_id,
            "status": "completed" if not errors else "failed",
            "records_seen": records_seen,
            "records_imported": records_imported,
            "duplicates": duplicates,
            "rejected": rejected,
            "errors": errors,
            "records": records,
        }

    async def fetch_date_range(
        self, start_date: date, end_date: date, dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Fetch records for a given date range.

        Args:
            start_date: Start of the date range.
            end_date: End of the date range.
            dry_run: If True, do not persist any records.

        Returns:
            Summary of the fetch operation.
        """
        source_run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC).isoformat()

        log_payload = {
            "source_run_id": source_run_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "dry_run": dry_run,
        }
        logger.info("Starting official portal fetch", extra=log_payload)

        if not dry_run:
            self.source_run_repo.create_run(
                source_run_id=source_run_id,
                source_id=self.source_id,
                run_type="scheduled_scrape",
                params_json=f'{{"start_date": "{start_date.isoformat()}", "end_date": "{end_date.isoformat()}"}}',
            )

        records_seen = 0
        records_imported = 0
        duplicates = 0
        rejected = 0
        errors: list[str] = []

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": PORTAL_URL,
            "Origin": "https://neu.insolvenzbekanntmachungen.de",
        }

        try:
            async with httpx.AsyncClient(
                headers=headers, follow_redirects=True, timeout=30.0
            ) as client:
                session = JSFSession(client)
                await session.initialize()

                # Realistic delay to avoid anti-bot detection (async version)
                await asyncio.sleep(1.5)

                form_data = {
                    "frm_suche:ldi_datumVon:datumHtml5": start_date.isoformat(),
                    "frm_suche:ldi_datumBis:datumHtml5": end_date.isoformat(),
                    "frm_suche:lsom_wildcard:lsom": "0",
                    "frm_suche:lsom_gegenstand:codelist:mysom": "NO_CODE",
                    "frm_suche:lsom_bundesland:codelist:scl_bundesland:mysom": "BE",
                    "frm_suche:lsi_insolvenzgerichte:codelist:scl_insolvenzgericht:mysom": "NO_CODE",
                    "frm_suche:litx_firmaNachName:text": "",
                    "frm_suche:litx_vorname:text": "",
                    "frm_suche:litx_sitzWohnsitz:text": "",
                    "frm_suche:iaz_aktenzeichen:itx_abteilung": "",
                    "frm_suche:iaz_aktenzeichen:itx_lfdNr": "",
                    "frm_suche:iaz_aktenzeichen:itx_jahr": "",
                    "frm_suche:iaz_aktenzeichen:ih_aktenzeichen": "true",
                    "frm_suche:ir_registereintrag:itx_registernummer": "",
                    "frm_suche:ir_registereintrag:ih_registereintrag": "true",
                    "frm_suche:cbt_suchen": "Suchen",
                }
                payload = session.get_payload(form_data)

                # Retry logic for robustness
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = await client.post(session.form_action, data=payload)

                        # Handle Cloudflare or anti-bot 403
                        if (
                            response.status_code == 403
                            or "cloudflare" in response.text.lower()
                        ):
                            error_msg = "blocked_by_anti_bot"
                            logger.error(
                                error_msg, extra={"status_code": response.status_code}
                            )
                            errors.append(error_msg)
                            break

                        response.raise_for_status()

                        if (
                            "frm_suche" in response.text
                            and "jakarta.faces.ViewState" in response.text
                            and "Suchergebnis" not in response.text
                        ):
                            error_msg = "search_form_returned_without_results"
                            logger.error(error_msg)
                            errors.append(error_msg)
                            break

                        records = self._parse_response(response.text)
                        records_seen, records_imported = self._persist_records(
                            source_run_id, records, dry_run
                        )
                        break  # Success, exit retry loop

                    except httpx.TimeoutException:
                        logger.warning(f"Timeout on attempt {attempt + 1}, retrying...")
                        await asyncio.sleep(2.0 * (attempt + 1))
                    except httpx.HTTPStatusError as e:
                        error_msg = f"HTTP error {e.response.status_code}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        break
                    except Exception as e:
                        error_msg = f"Unexpected error: {e!s}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        break

        except Exception as e:
            error_msg = f"Session initialization failed: {e!s}"
            logger.error(error_msg)
            errors.append(error_msg)

        completed_at = datetime.now(UTC).isoformat()

        if not dry_run:
            self.source_run_repo.complete_run(
                source_run_id=source_run_id,
                records_seen=records_seen,
                records_imported=records_imported,
                duplicates=duplicates,
                rejected=rejected,
                error_json=json.dumps(errors) if errors else None,
            )

        logger.info(
            "Official portal fetch completed",
            extra={
                "source_run_id": source_run_id,
                "status": "completed" if not errors else "failed",
                "records_seen": records_seen,
                "records_imported": records_imported,
            },
        )

        return {
            "source_run_id": source_run_id,
            "status": "completed" if not errors else "failed",
            "records_seen": records_seen,
            "records_imported": records_imported,
            "duplicates": duplicates,
            "rejected": rejected,
            "errors": errors,
            "records": records if "records" in locals() else [],
        }

    def _extract_records_from_table(self, table: Any) -> list[dict[str, Any]]:
        """Extract raw record dictionaries from an HTML table."""
        records: list[dict[str, Any]] = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            company_name = cells[0].get_text(strip=True)
            court = cells[1].get_text(strip=True)
            case_number = cells[2].get_text(strip=True)
            pub_date_str = cells[3].get_text(strip=True)
            normalized_pub_date = _normalize_publication_date(pub_date_str)
            stage = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            legal_form = _infer_legal_form(company_name)
            records.append(
                {
                    "external_id": f"{court}_{case_number}",
                    "company_name": company_name,
                    "legal_form": legal_form,
                    "court": court,
                    "case_number": case_number,
                    "publication_date": normalized_pub_date,
                    "proceeding_stage": stage,
                    "raw_text": row.get_text(strip=True, separator=" | "),
                    "source_url": PORTAL_URL,
                }
            )
        return records

    def _parse_html_results(self, html: str) -> list[dict[str, Any]]:
        """Parse a full HTML search results page into raw record dictionaries."""
        soup = BeautifulSoup(html, "html.parser")
        candidate_tables = soup.find_all("table")
        records: list[dict[str, Any]] = []
        for table in candidate_tables:
            table_records = self._extract_records_from_table(table)
            if table_records:
                records.extend(table_records)
        return records

    def _parse_response(self, html_or_xml: str) -> list[dict[str, Any]]:
        """Parse the portal response into raw record dictionaries."""
        records = []
        try:
            sanitized = re.sub(
                r"^\s*(<!--.*?-->\s*)+", "", html_or_xml, flags=re.DOTALL
            )
            if (
                sanitized.lstrip().startswith("<!DOCTYPE html")
                or "<html" in sanitized[:512].lower()
            ):
                records = self._parse_html_results(sanitized)
                logger.info(f"Parsed {len(records)} records from HTML response")
                return records

            root = ET.fromstring(sanitized)
            for update in root.findall(".//update"):
                update_id = update.get("id", "")
                if "resultsTable" not in update_id and "results" not in update_id:
                    continue
                cdata_content = update.text
                if not cdata_content:
                    continue
                soup = BeautifulSoup(cdata_content, "html.parser")
                table = soup.find("table")
                if not table:
                    continue
                records.extend(self._extract_records_from_table(table))
            logger.info(f"Parsed {len(records)} records from JSF response")
        except ET.ParseError as e:
            logger.error(f"Failed to parse JSF XML response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}")

        return records
