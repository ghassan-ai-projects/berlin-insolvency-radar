"""Unit tests for domain compliance module."""

from biradar.domain.compliance import (
    evaluate_compliance,
    has_consumer_indicators,
    is_allowed_corporate_form,
)


def test_allowed_corporate_forms():
    assert is_allowed_corporate_form("GmbH") is True
    assert is_allowed_corporate_form("UG") is True
    assert is_allowed_corporate_form("AG") is True
    assert is_allowed_corporate_form("GmbH & Co. KG") is True
    assert is_allowed_corporate_form("e.K.") is False
    assert is_allowed_corporate_form(None) is False


def test_consumer_indicators():
    assert (
        has_consumer_indicators("Privatinsolvenz von Max Mustermann", "Max Mustermann")
        is True
    )
    assert has_consumer_indicators("Verbraucherschutzverfahren", "Test GmbH") is True
    assert has_consumer_indicators("Normale Insolvenz einer GmbH", "Test GmbH") is False


def test_evaluate_compliance():
    is_allowed, reason = evaluate_compliance("GmbH", "Normale Insolvenz", "Test GmbH")
    assert is_allowed is True
    assert reason is None

    is_allowed, reason = evaluate_compliance(
        "e.K.", "Privatinsolvenz", "Max Mustermann"
    )
    assert is_allowed is False
    assert reason == "consumer_or_personal_indicator_detected"

    is_allowed, reason = evaluate_compliance(None, "Some text", "Unknown Entity")
    assert is_allowed is False
    assert reason == "missing_or_unsupported_legal_form"
