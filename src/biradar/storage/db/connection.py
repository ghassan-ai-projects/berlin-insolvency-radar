"""DuckDB connection lifecycle and the migration runner."""

from pathlib import Path

import duckdb

from biradar.storage.db.migrations import MIGRATIONS


class Database:
    """Manages the DuckDB connection and schema initialization."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))

    def close(self) -> None:
        self.conn.close()

    def begin(self) -> None:
        self.conn.execute("BEGIN TRANSACTION")

    def commit(self) -> None:
        self.conn.execute("COMMIT")

    def rollback(self) -> None:
        self.conn.execute("ROLLBACK")

    def run_migrations(self) -> None:
        """Run database schema migrations."""
        self._ensure_schema_migrations_table()
        for name, migration_fn in MIGRATIONS:
            if self._migration_applied(name):
                continue
            migration_fn(self.conn)
            self._record_migration(name)

    def get_schema_version(self) -> str:
        cursor = self.conn.execute(
            "SELECT migration_name FROM schema_migrations ORDER BY migration_name DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else "unmigrated"

    def _ensure_schema_migrations_table(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_name VARCHAR PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    def _migration_applied(self, name: str) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM schema_migrations WHERE migration_name = ?", [name]
        )
        return cursor.fetchone() is not None

    def _record_migration(self, name: str) -> None:
        self.conn.execute(
            "INSERT INTO schema_migrations (migration_name) VALUES (?)", [name]
        )


def scalar_count(conn: duckdb.DuckDBPyConnection, sql: str) -> int:
    """Run an aggregate query and return its single scalar result.

    ``fetchone()`` is typed as Optional, which is correct in general but never
    the case for an aggregate. This narrows the type once here instead of
    suppressing reportOptionalSubscript across the codebase.
    """
    row = conn.execute(sql).fetchone()
    if row is None:
        raise RuntimeError(f"Aggregate query returned no row: {sql}")
    return int(row[0])
