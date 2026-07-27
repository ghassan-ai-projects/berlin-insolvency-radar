"""Unit tests for database helpers and migration bookkeeping."""

import duckdb
import pytest

from biradar.storage.db import (
    LATEST_SCHEMA_VERSION,
    MIGRATION_SEQUENCE,
    Database,
    compute_content_hash,
    scalar_count,
)


@pytest.fixture
def conn():
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE TABLE t (v INTEGER)")
    return connection


def test_scalar_count_returns_zero_for_empty_table(conn):
    assert scalar_count(conn, "SELECT COUNT(*) FROM t") == 0


def test_scalar_count_returns_row_count(conn):
    conn.execute("INSERT INTO t VALUES (1), (2), (3)")
    assert scalar_count(conn, "SELECT COUNT(*) FROM t") == 3


def test_scalar_count_honours_where_clause(conn):
    conn.execute("INSERT INTO t VALUES (1), (2), (3)")
    assert scalar_count(conn, "SELECT COUNT(*) FROM t WHERE v > 1") == 2


def test_scalar_count_returns_int_type(conn):
    assert isinstance(scalar_count(conn, "SELECT COUNT(*) FROM t"), int)


def test_scalar_count_raises_when_query_yields_no_row(conn):
    """A non-aggregate query over an empty table has no row to unpack."""
    with pytest.raises(RuntimeError, match="no row"):
        scalar_count(conn, "SELECT v FROM t")


def test_compute_content_hash_is_stable_and_prefixed():
    assert compute_content_hash("abc") == compute_content_hash("abc")
    assert compute_content_hash("abc").startswith("sha256:")


def test_compute_content_hash_matches_for_str_and_bytes():
    assert compute_content_hash("abc") == compute_content_hash(b"abc")


def test_compute_content_hash_differs_for_different_input():
    assert compute_content_hash("abc") != compute_content_hash("abd")


def test_run_migrations_records_full_sequence(tmp_path):
    db = Database(tmp_path / "t.duckdb")
    try:
        db.run_migrations()
        applied = [
            row[0]
            for row in db.conn.execute(
                "SELECT migration_name FROM schema_migrations ORDER BY migration_name"
            ).fetchall()
        ]
        assert applied == sorted(MIGRATION_SEQUENCE)
        assert db.get_schema_version() == LATEST_SCHEMA_VERSION
    finally:
        db.close()


def test_run_migrations_is_idempotent(tmp_path):
    db = Database(tmp_path / "t.duckdb")
    try:
        db.run_migrations()
        db.run_migrations()
        assert scalar_count(db.conn, "SELECT COUNT(*) FROM schema_migrations") == len(
            MIGRATION_SEQUENCE
        )
    finally:
        db.close()


def test_get_schema_version_reports_unmigrated_before_migrations(tmp_path):
    db = Database(tmp_path / "t.duckdb")
    try:
        db.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(migration_name VARCHAR PRIMARY KEY, applied_at TIMESTAMP)"
        )
        assert db.get_schema_version() == "unmigrated"
    finally:
        db.close()


def test_database_creates_parent_directory(tmp_path):
    db = Database(tmp_path / "nested" / "dir" / "t.duckdb")
    try:
        assert (tmp_path / "nested" / "dir").is_dir()
    finally:
        db.close()


def test_rollback_discards_uncommitted_writes(tmp_path):
    db = Database(tmp_path / "t.duckdb")
    try:
        db.run_migrations()
        db.begin()
        db.conn.execute(
            "INSERT INTO candidates (candidate_id, canonical_company_name, status) "
            "VALUES ('c1', 'Acme GmbH', 'raw_candidate')"
        )
        db.rollback()
        assert scalar_count(db.conn, "SELECT COUNT(*) FROM candidates") == 0
    finally:
        db.close()


def test_commit_persists_writes(tmp_path):
    db = Database(tmp_path / "t.duckdb")
    try:
        db.run_migrations()
        db.begin()
        db.conn.execute(
            "INSERT INTO candidates (candidate_id, canonical_company_name, status) "
            "VALUES ('c1', 'Acme GmbH', 'raw_candidate')"
        )
        db.commit()
        assert scalar_count(db.conn, "SELECT COUNT(*) FROM candidates") == 1
    finally:
        db.close()
