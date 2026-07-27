"""Unit tests for domain date validation."""

import duckdb
import pytest

from biradar.domain.validation import validate_date_field


def test_validate_date_field_passes_through_valid_iso_date():
    assert validate_date_field("2026-02-15") == "2026-02-15"


def test_validate_date_field_accepts_leap_day_in_leap_year():
    assert validate_date_field("2024-02-29") == "2024-02-29"


def test_validate_date_field_returns_none_for_none():
    assert validate_date_field(None) is None


@pytest.mark.parametrize(
    "value",
    [
        "2026-02-30",  # day out of range for month
        "2026-13-01",  # month out of range
        "2026-00-10",  # zero month
        "2026-01-00",  # zero day
        "2025-02-29",  # not a leap year
    ],
)
def test_validate_date_field_rejects_calendar_invalid_dates(value):
    assert validate_date_field(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "20260215",  # basic ISO form, parsed by fromisoformat but rejected by DuckDB
        "2026-W01-1",  # ISO week date, same
        "2026-2-15",  # unpadded
        "15.02.2026",  # German portal format
        "not-a-date",
        "",
    ],
)
def test_validate_date_field_rejects_formats_duckdb_cannot_store(value):
    assert validate_date_field(value) is None


def test_validate_date_field_logs_warning_on_rejection(caplog):
    with caplog.at_level("WARNING"):
        validate_date_field("2026-02-30")
    assert "2026-02-30" in caplog.text


@pytest.mark.parametrize(
    "value",
    ["2026-02-30", "2026-13-01", "20260215", "2026-W01-1", "15.02.2026"],
)
def test_rejected_values_would_otherwise_break_duckdb_date_column(value):
    """Guard the premise: every rejected value really is unstorable as a DATE."""
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE t (d DATE)")
    with pytest.raises(duckdb.ConversionException):
        conn.execute("INSERT INTO t VALUES (?)", [value])


def test_accepted_value_is_storable_in_duckdb_date_column():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE t (d DATE)")
    validated = validate_date_field("2026-02-15")
    conn.execute("INSERT INTO t VALUES (?)", [validated])
    assert conn.execute("SELECT d FROM t").fetchone()[0].isoformat() == "2026-02-15"
