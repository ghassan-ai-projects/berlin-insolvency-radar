"""Typed extraction of legacy filing rows."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class FilingRow:
    """String-coerced view of one legacy ``filings`` row."""

    company_name: str
    legal_form: str
    raw_text: str
    court: str
    case_number: str
    publication_date: str
    publication_type: str
    register_number: str
    source_url: str
    filing_id: str
    scraped_at: str


def _str_field(row_dict: dict[str, Any], name: str) -> str:
    return str(row_dict.get(name, "") or "")


def extract_filing_row(row_dict: dict[str, Any]) -> FilingRow:
    """Coerce one raw legacy row dict into import-ready strings.

    A missing ``filing_id`` gets a generated ``leg_`` id and a missing
    ``scraped_at`` falls back to the current time; the dry run reads only
    the shared text fields.
    """
    return FilingRow(
        company_name=_str_field(row_dict, "company_name"),
        legal_form=_str_field(row_dict, "legal_form"),
        raw_text=_str_field(row_dict, "raw_text"),
        court=_str_field(row_dict, "court"),
        case_number=_str_field(row_dict, "case_number"),
        publication_date=_str_field(row_dict, "publication_date"),
        publication_type=_str_field(row_dict, "publication_type"),
        register_number=_str_field(row_dict, "register_number"),
        source_url=_str_field(row_dict, "source_url"),
        filing_id=str(row_dict.get("filing_id", "") or f"leg_{uuid.uuid4().hex}"),
        scraped_at=str(row_dict.get("scraped_at", "") or datetime.now(UTC).isoformat()),
    )
