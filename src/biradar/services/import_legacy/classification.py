"""Compliance gate and candidate status classification for legacy rows."""

from dataclasses import dataclass
from typing import Any

from biradar.domain.compliance import evaluate_compliance
from biradar.services.import_legacy.rows import FilingRow


@dataclass(frozen=True)
class Classification:
    """Import disposition of one filing row."""

    status: str
    risk_flags: list[str]


def is_compliant(row: FilingRow) -> bool:
    """Return the compliance verdict for the coerced filing text."""
    allowed, _reason = evaluate_compliance(
        row.legal_form, row.raw_text, row.company_name
    )
    return allowed


def is_malformed(row: FilingRow) -> bool:
    """True when court, case number, or publication date is missing."""
    return not row.court or not row.case_number or not row.publication_date


def malformed_warning(filing_label: Any) -> str:
    """Render the shared malformed-row warning.

    Callers pass different labels on purpose: the dry run passes the raw
    ``row_dict.get("filing_id")`` (which may render ``None``), the real
    import passes the coerced ``row.filing_id``.
    """
    return (
        f"Malformed row {filing_label}: missing court, case number, "
        "or publication date."
    )


def classify_candidate(row: FilingRow) -> Classification:
    """Derive candidate status and risk flags from row completeness."""
    if is_malformed(row):
        return Classification(
            status="needs_review", risk_flags=["malformed_source_row"]
        )
    if not row.legal_form or row.legal_form.strip() == "":
        return Classification(status="needs_review", risk_flags=["missing_legal_form"])
    return Classification(status="review_ready", risk_flags=[])
