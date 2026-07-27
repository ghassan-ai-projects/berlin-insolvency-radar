"""Unit tests for LangGraph checkpoint management.

NOTE: `langgraph-checkpoint-sqlite` is not a declared dependency, so at runtime
`SqliteSaver` is None and the manager always falls back to MemorySaver. The
SQLite branch is therefore exercised by injecting a saver, which both covers the
code and pins the behaviour that branch is supposed to have if the dependency is
ever added. See test_sqlite_saver_is_unavailable_in_this_environment.
"""

import sqlite3

import pytest
from langgraph.checkpoint.memory import MemorySaver

from biradar.graph import checkpoints as checkpoints_module
from biradar.graph.checkpoints import CheckpointManager


@pytest.fixture
def with_sqlite_saver(monkeypatch):
    """Enable the SQLite branch with a stand-in saver."""

    class FakeSqliteSaver:
        def __init__(self, conn):
            self.conn = conn

    monkeypatch.setattr(checkpoints_module, "SqliteSaver", FakeSqliteSaver)
    return FakeSqliteSaver


def test_sqlite_saver_is_unavailable_in_this_environment():
    """Pins the real gap: the dependency providing SqliteSaver is not installed."""
    assert checkpoints_module.SqliteSaver is None


def test_defaults_to_memory_saver_for_a_file_path_without_the_dependency(tmp_path):
    mgr = CheckpointManager(tmp_path / "cp.sqlite")
    try:
        assert isinstance(mgr.saver_instance, MemorySaver)
        assert not (tmp_path / "cp.sqlite").exists()
    finally:
        mgr.close()


def test_uses_memory_saver_for_in_memory_path():
    mgr = CheckpointManager(":memory:")
    try:
        assert isinstance(mgr.saver_instance, MemorySaver)
        assert mgr.db_path is None
    finally:
        mgr.close()


def test_uses_sqlite_saver_when_dependency_is_present(tmp_path, with_sqlite_saver):
    mgr = CheckpointManager(tmp_path / "cp.sqlite")
    try:
        assert isinstance(mgr.saver_instance, with_sqlite_saver)
        assert (tmp_path / "cp.sqlite").exists()
    finally:
        mgr.close()


def test_sqlite_branch_creates_parent_directory(tmp_path, with_sqlite_saver):
    mgr = CheckpointManager(tmp_path / "nested" / "dir" / "cp.sqlite")
    try:
        assert (tmp_path / "nested" / "dir").is_dir()
    finally:
        mgr.close()


def test_sqlite_checkpoint_file_is_owner_only_readable(tmp_path, with_sqlite_saver):
    """Checkpoints hold pipeline state; they must not be group/world readable."""
    mgr = CheckpointManager(tmp_path / "cp.sqlite")
    try:
        assert (tmp_path / "cp.sqlite").stat().st_mode & 0o077 == 0
    finally:
        mgr.close()


def test_sqlite_branch_enables_wal_journal_mode(tmp_path, with_sqlite_saver):
    mgr = CheckpointManager(tmp_path / "cp.sqlite")
    try:
        mode = mgr._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        mgr.close()


def test_close_is_idempotent_for_memory_saver():
    mgr = CheckpointManager(":memory:")
    mgr.close()
    mgr.close()


def test_clear_thread_is_a_noop_for_memory_saver():
    mgr = CheckpointManager(":memory:")
    try:
        mgr.clear_thread("thread-1")
    finally:
        mgr.close()


def test_clear_thread_removes_only_the_named_thread(tmp_path, with_sqlite_saver):
    db_path = tmp_path / "cp.sqlite"
    mgr = CheckpointManager(db_path)
    mgr.close()

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS checkpoints (thread_id TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS checkpoint_writes (thread_id TEXT)")
        conn.executemany(
            "INSERT INTO checkpoints VALUES (?)", [("keep",), ("drop",), ("drop",)]
        )
        conn.execute("INSERT INTO checkpoint_writes VALUES ('drop')")

    manager = CheckpointManager(db_path)
    try:
        manager.clear_thread("drop")
    finally:
        manager.close()

    with sqlite3.connect(str(db_path)) as conn:
        remaining = [r[0] for r in conn.execute("SELECT thread_id FROM checkpoints")]
        writes = conn.execute("SELECT COUNT(*) FROM checkpoint_writes").fetchone()[0]

    assert remaining == ["keep"]
    assert writes == 0
