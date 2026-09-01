"""Cursor-to-dict mapping helpers shared by the repository modules."""

from typing import Any


def rows_as_dicts(cursor: Any) -> list[dict[str, Any]]:
    """Map all rows of an executed cursor to dicts keyed by column name."""
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def single_row_as_dict(cursor: Any) -> dict[str, Any] | None:
    """Map the first row of an executed cursor to a dict, or None if absent."""
    row = cursor.fetchone()
    if not row:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))
