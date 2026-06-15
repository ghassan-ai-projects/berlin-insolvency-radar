"""Unit tests for deterministic deduplication keys."""

from biradar.domain.dedupe import compute_dedupe_key, normalize_string


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
