"""Parsing of portal result pages (HTML table, span layout) into records."""

import re
from typing import Any

from bs4 import BeautifulSoup

from biradar.sources.official_portal.constants import PORTAL_URL
from biradar.sources.official_portal.value_normalization import (
    _infer_legal_form,
    _normalize_publication_date,
)
from biradar.utils.html import attr_str


def make_record(
    company_name: str,
    court: str,
    case_number: str,
    register_number: str,
    publication_date: str,
    raw_text: str,
) -> dict[str, Any]:
    """Build one raw record dict with a normalized publication date."""
    return {
        "external_id": f"{court}_{case_number}",
        "company_name": company_name,
        "legal_form": _infer_legal_form(company_name),
        "court": court,
        "case_number": case_number,
        "register_number": register_number,
        "publication_date": _normalize_publication_date(publication_date),
        "raw_text": raw_text,
        "source_url": PORTAL_URL,
    }


def extract_records_from_table(table: Any) -> list[dict[str, Any]]:
    """Extract raw record dictionaries from an HTML table.

    Portal table columns (tbl_ergebnis):
    [0] publication_date  [1] case_number  [2] court
    [3] company_name      [4] seat         [5] register_number
    [6] detail form button (empty text)
    """
    records: list[dict[str, Any]] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        publication_date = cells[0].get_text(strip=True)
        case_number = cells[1].get_text(strip=True)
        court = cells[2].get_text(strip=True)
        company_name = cells[3].get_text(strip=True)
        register_number = cells[5].get_text(strip=True) if len(cells) > 5 else ""
        records.append(
            make_record(
                company_name=company_name,
                court=court,
                case_number=case_number,
                register_number=register_number,
                publication_date=publication_date,
                raw_text=row.get_text(strip=True, separator=" | "),
            )
        )
    return records


def parse_html_results(html: str) -> list[dict[str, Any]]:
    """Parse a full HTML search results page into raw record dictionaries."""
    soup = BeautifulSoup(html, "html.parser")
    result_table = soup.find("table", id="tbl_ergebnis")
    if result_table:
        return extract_records_from_table(result_table)
    span_records = extract_records_from_span_results(soup)
    if span_records:
        return span_records
    # Fallback: try any table with enough columns
    for table in soup.find_all("table"):
        records = extract_records_from_table(table)
        if records:
            return records
    return []


def extract_records_from_span_results(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Extract result rows from the modern span/div-based portal layout."""
    grouped_fields = _group_span_fields(soup)

    records: list[dict[str, Any]] = []
    for row_idx in sorted(grouped_fields.keys(), key=int):
        fields = grouped_fields[row_idx]
        (
            publication_date,
            case_number,
            court,
            company_name,
            register_number,
        ) = _field_values(fields)

        if not company_name or not court or not case_number:
            continue

        raw_text = " | ".join(value for value in fields.values() if value)
        records.append(
            make_record(
                company_name=company_name,
                court=court,
                case_number=case_number,
                register_number=register_number,
                publication_date=publication_date,
                raw_text=raw_text,
            )
        )
    return records


def _group_span_fields(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    """Group span nodes with tbl_ergebnis:<row>:otx_<field> ids by row."""
    grouped_fields: dict[str, dict[str, str]] = {}
    for node in soup.find_all(id=re.compile(r"tbl_ergebnis:\d+:otx_")):
        node_id = attr_str(node, "id", "") or ""
        match = re.match(r"tbl_ergebnis:(\d+):otx_([^:]+)", node_id)
        if not match:
            continue
        row_idx, field_name = match.groups()
        grouped_fields.setdefault(row_idx, {})[field_name.lower()] = node.get_text(
            strip=True
        )
    return grouped_fields


def _field_values(fields: dict[str, str]) -> tuple[str, str, str, str, str]:
    """Map heuristically named span fields to (date, case, court, name, register)."""
    publication_date = ""
    case_number = ""
    court = ""
    company_name = ""
    register_number = ""

    for field_name, value in fields.items():
        if not publication_date and "datum" in field_name:
            publication_date = value
        elif not case_number and ("aktenzeichen" in field_name or field_name == "az"):
            case_number = value
        elif not court and "gericht" in field_name:
            court = value
        elif not company_name and any(
            marker in field_name
            for marker in ("schuldner", "firma", "name", "bezeichnung")
        ):
            company_name = value
        elif not register_number and "register" in field_name:
            register_number = value

    return publication_date, case_number, court, company_name, register_number
