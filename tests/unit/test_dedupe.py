"""Unit tests for deterministic deduplication keys."""

from biradar.domain.dedupe import (
    compute_dedupe_key,
    deduplicate_candidates,
    normalize_string,
)


def test_normalize_string_for_matching():
    assert normalize_string(" Example GmbH & Co. KG, ") == "example gmbh and co kg"
    assert normalize_string(None) == ""


def test_compute_dedupe_key_is_stable_for_same_candidate():
    first_key = compute_dedupe_key(
        company_name="Example GmbH & Co. KG",
        court="Charlottenburg (Berlin)",
        case_number="36e IN 123/26",
        publication_date="2026-06-15",
    )
    second_key = compute_dedupe_key(
        company_name=" example gmbh and co kg. ",
        court="Charlottenburg (Berlin)",
        case_number="36e IN 123/26",
        publication_date="2026-06-15",
    )

    assert first_key == second_key
    assert first_key.startswith("dedupe_")


def test_compute_dedupe_key_changes_for_different_case():
    first_key = compute_dedupe_key(
        company_name="Example GmbH",
        court="Charlottenburg (Berlin)",
        case_number="36e IN 123/26",
        publication_date="2026-06-15",
    )
    second_key = compute_dedupe_key(
        company_name="Example GmbH",
        court="Charlottenburg (Berlin)",
        case_number="36e IN 124/26",
        publication_date="2026-06-15",
    )

    assert first_key != second_key


def test_deduplicate_candidates_marks_duplicates():
    candidates = [
        {
            "candidate_id": "1",
            "company_name": "Example GmbH",
            "court": "Charlottenburg",
            "case_number": "123/26",
            "publication_date": "2026-06-15",
            "status": "raw_candidate",
        },
        {
            "candidate_id": "2",
            "company_name": " Example gmbh. ",
            "court": "Charlottenburg",
            "case_number": "123/26",
            "publication_date": "2026-06-15",
            "status": "raw_candidate",
        },
    ]

    result = deduplicate_candidates(candidates)

    assert result[0]["status"] == "deduped_candidate"
    assert result[0]["candidate_id"] == "1"

    assert result[1]["status"] == "duplicate"
    assert result[1]["canonical_candidate_id"] == "1"


def test_deduplicate_candidates_ignores_quarantined():
    candidates = [
        {
            "candidate_id": "1",
            "company_name": "Example GmbH",
            "court": "Charlottenburg",
            "case_number": "123/26",
            "publication_date": "2026-06-15",
            "status": "quarantined",
        },
        {
            "candidate_id": "2",
            "company_name": "Example GmbH",
            "court": "Charlottenburg",
            "case_number": "123/26",
            "publication_date": "2026-06-15",
            "status": "raw_candidate",
        },
    ]

    result = deduplicate_candidates(candidates)

    # First is quarantined, stays quarantined
    assert result[0]["status"] == "quarantined"
    # Second becomes canonical since the first was ignored for dedupe
    assert result[1]["status"] == "deduped_candidate"
    assert result[1]["candidate_id"] == "2"


def test_deduplicate_candidates_does_not_mutate_input():
    """domain/ must be side-effect free: callers keep their own dicts intact."""
    candidates = [
        {
            "candidate_id": "cand_1",
            "company_name": "Acme GmbH",
            "court": "AG Charlottenburg",
            "case_number": "36e IN 1/26",
            "publication_date": "2026-06-15",
            "status": "deduped_candidate",
        },
        {
            "candidate_id": "cand_2",
            "company_name": "Acme GmbH",
            "court": "AG Charlottenburg",
            "case_number": "36e IN 1/26",
            "publication_date": "2026-06-15",
            "status": "deduped_candidate",
        },
    ]
    before = [dict(c) for c in candidates]

    result = deduplicate_candidates(candidates)

    assert candidates == before, "input dicts were mutated"
    assert result[1]["status"] == "duplicate"
    assert "canonical_candidate_id" not in candidates[1]


def test_deduplicate_candidates_returns_new_dict_objects():
    candidates = [{"candidate_id": "cand_1", "company_name": "Acme GmbH"}]

    result = deduplicate_candidates(candidates)

    assert result[0] is not candidates[0]


def test_deduplicate_candidates_copies_quarantined_records_too():
    candidates = [{"candidate_id": "cand_1", "status": "quarantined"}]

    result = deduplicate_candidates(candidates)

    assert result[0] is not candidates[0]
    assert result[0]["status"] == "quarantined"


def test_deduplicate_candidates_accepts_readonly_mappings():
    """Signature widened to Sequence[Mapping]; a MappingProxy must work."""
    from types import MappingProxyType

    candidates = [MappingProxyType({"candidate_id": "cand_1", "company_name": "Acme"})]

    result = deduplicate_candidates(candidates)

    assert result[0]["status"] == "deduped_candidate"
