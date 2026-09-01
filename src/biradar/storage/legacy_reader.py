"""Read-only access to external legacy DuckDB files."""

import logging
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


def read_filings_read_only(path: Path) -> list[dict[str, Any]]:
    """Return every row of the legacy ``filings`` table as a dict.

    Opens the database read-only and closes the connection before returning;
    the legacy file is never written to.
    """
    conn = duckdb.connect(str(path), read_only=True)
    cursor = conn.execute("SELECT * FROM filings")
    cols = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(cols, row)) for row in rows]
