"""Deterministic deduplication logic for candidates."""

import hashlib


def normalize_string(s: str | None) -> str:
    """Normalize a string for comparison (lowercase, strip, remove punctuation)."""
    if not s:
        return ""
    return s.strip().lower().replace(".", "").replace(",", "").replace("&", "and")


def compute_dedupe_key(
    company_name: str | None,
    court: str | None,
    case_number: str | None,
    publication_date: str | None,
) -> str:
    """
    Compute a deterministic deduplication key.

    Canonical key is based on: normalized company name + court + case number + publication date.
    """
    norm_name = normalize_string(company_name)
    norm_court = normalize_string(court)
    norm_case = normalize_string(case_number)
    norm_date = normalize_string(publication_date)

    composite = f"{norm_name}|{norm_court}|{norm_case}|{norm_date}"
    return f"dedupe_{hashlib.sha256(composite.encode('utf-8')).hexdigest()[:16]}"
