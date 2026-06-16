"""Official portal source adapter for neu.insolvenzbekanntmachungen.de.

This adapter implements robust JSF session management, including extracting
and replaying `javax.faces.ViewState` and handling CSRF tokens, along with
realistic delays and headers to avoid anti-bot blocking.
"""

import asyncio
import hashlib
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

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


class JSFSession:
    """Manages JSF session state, including ViewState and cookies."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.view_state: str | None = None
        self.token: str | None = None

    async def initialize(self) -> None:
        """Initialize the session by fetching the initial page and extracting JSF state."""
        logger.info("Initializing JSF session for official portal")
        response = await self.client.get(PORTAL_URL, timeout=15.0)
        response.raise_for_status()

        html = response.text
        # Extract javax.faces.ViewState
        view_state_match = re.search(
            r'<input[^>]*name="javax\.faces\.ViewState"[^>]*value="([^"]*)"', html
        )
        if view_state_match:
            self.view_state = view_state_match.group(1)
            logger.debug("Extracted javax.faces.ViewState")
        else:
            logger.warning("Could not extract javax.faces.ViewState")

        # Extract CSRF token if present (often named 'token' or similar in JSF)
        token_match = re.search(r'<input[^>]*name="token"[^>]*value="([^"]*)"', html)
        if token_match:
            self.token = token_match.group(1)
            logger.debug("Extracted CSRF token")

    def get_payload(self, form_data: dict[str, Any]) -> dict[str, Any]:
        """Build the JSF POST payload with required state fields."""
        payload = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "form:searchButton",
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": "form:results",
            "javax.faces.behavior.event": "action",
            "javax.faces.partial.event": "click",
        }
        if self.view_state:
            payload["javax.faces.ViewState"] = self.view_state
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
        started_at = datetime.now(timezone.utc).isoformat()

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
            async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=30.0) as client:
                session = JSFSession(client)
                await session.initialize()

                # Realistic delay to avoid anti-bot detection (async version)
                await asyncio.sleep(1.5)

                form_data = {
                    "form:court": "",  # Empty for all courts, or specific code
                    "form:startDate": start_date.strftime("%d.%m.%Y"),
                    "form:endDate": end_date.strftime("%d.%m.%Y"),
                }
                payload = session.get_payload(form_data)

                # Retry logic for robustness
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = await client.post(PORTAL_URL, data=payload)
                        
                        # Handle Cloudflare or anti-bot 403
                        if response.status_code == 403 or "cloudflare" in response.text.lower():
                            error_msg = "blocked_by_anti_bot"
                            logger.error(error_msg, extra={"status_code": response.status_code})
                            errors.append(error_msg)
                            break

                        response.raise_for_status()
                        
                        # Parse response (simplified for this implementation)
                        records = self._parse_response(response.text)
                        records_seen = len(records)

                        for record in records:
                            raw_text = record.get("raw_text", "")
                            content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
                            
                            raw_record_id = f"raw_{uuid.uuid4().hex}"
                            retrieved_at = datetime.now(timezone.utc).isoformat()

                            if not dry_run:
                                # repository handles deduplication and persistence
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
                                
                                # For simplicity, we assume all parsed records are imported.
                                # In a full implementation, we'd check if it was a duplicate here 
                                # or let the candidate dedupe logic handle it later.
                                records_imported += 1
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
                        error_msg = f"Unexpected error: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        break

        except Exception as e:
            error_msg = f"Session initialization failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        completed_at = datetime.now(timezone.utc).isoformat()
        
        if not dry_run:
            self.source_run_repo.complete_run(
                source_run_id=source_run_id,
                records_seen=records_seen,
                records_imported=records_imported,
                duplicates=duplicates,
                rejected=rejected,
                error_json=str(errors) if errors else None,
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

    def _parse_response(self, html_or_xml: str) -> list[dict[str, Any]]:
        """
        Parse the JSF partial response XML into a list of raw record dictionaries.
        """
        records = []
        try:
            sanitized = re.sub(r"^\s*(<!--.*?-->\s*)+", "", html_or_xml, flags=re.DOTALL)
            # Parse the XML response
            root = ET.fromstring(sanitized)
            
            # Find all <update> elements
            for update in root.findall(".//update"):
                update_id = update.get("id", "")
                
                # We are looking for the table results, usually in 'form:resultsTable' or similar
                if "resultsTable" in update_id or "results" in update_id:
                    cdata_content = update.text
                    if not cdata_content:
                        continue
                        
                    # Parse the HTML inside the CDATA
                    soup = BeautifulSoup(cdata_content, "html.parser")
                    
                    # Find the table and iterate over rows
                    table = soup.find("table")
                    if not table:
                        continue
                        
                    for row in table.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 4:
                            # Typical columns: Company Name, Court, Case Number, Date, Stage, etc.
                            # Adjust indices based on actual portal layout
                            company_name = cells[0].get_text(strip=True)
                            court = cells[1].get_text(strip=True)
                            case_number = cells[2].get_text(strip=True)
                            pub_date_str = cells[3].get_text(strip=True)
                            stage = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                            legal_form = _infer_legal_form(company_name)
                            
                            records.append({
                                "external_id": f"{court}_{case_number}",
                                "company_name": company_name,
                                "legal_form": legal_form,
                                "court": court,
                                "case_number": case_number,
                                "publication_date": pub_date_str,
                                "proceeding_stage": stage,
                                "raw_text": row.get_text(strip=True, separator=" | "),
                                "source_url": PORTAL_URL, # Base URL, actual detail URL would be constructed
                            })
            logger.info(f"Parsed {len(records)} records from JSF response")
        except ET.ParseError as e:
            logger.error(f"Failed to parse JSF XML response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}")
            
        return records
