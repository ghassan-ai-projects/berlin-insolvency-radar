"""Deterministic deduplication logic for candidates."""

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any


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


def deduplicate_candidates(
    candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """
    Deterministic deduplication of candidate records.

    Groups candidates by dedupe key and keeps the first valid corporate record.
    Others are marked as 'duplicate'.

    Pure: the input dicts are never mutated. Each returned record is a new dict,
    matching the zero-side-effects rule for `domain/` and the `{**state}` copy
    convention used by the LangGraph nodes that call this.
    """
    seen_keys: dict[str, str] = {}
    deduped_candidates = []

    for candidate in candidates:
        if candidate.get("status") == "quarantined":
            deduped_candidates.append({**candidate})
            continue

        key = compute_dedupe_key(
            company_name=candidate.get("company_name"),
            court=candidate.get("court"),
            case_number=candidate.get("case_number"),
            publication_date=candidate.get("publication_date"),
        )

        if key in seen_keys:
            # Mark as duplicate, link to canonical
            deduped_candidates.append(
                {
                    **candidate,
                    "status": "duplicate",
                    "canonical_candidate_id": seen_keys[key],
                }
            )
        else:
            # First time seeing this key, mark as canonical
            seen_keys[key] = candidate.get(
                "candidate_id", key.replace("dedupe_", "cand_")
            )
            deduped_candidates.append(
                {
                    **candidate,
                    "candidate_id": seen_keys[key],
                    "status": "deduped_candidate",
                }
            )

    return deduped_candidates
