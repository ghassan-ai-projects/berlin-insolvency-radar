"""Domain validation utilities."""

import logging
import re
from datetime import date

logger = logging.getLogger(__name__)

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_date_field(value: str | None) -> str | None:
    """Validate a string is a proper ISO date before passing to DuckDB DATE column.

    Both checks are required. The regex rejects formats DuckDB will not accept but
    ``date.fromisoformat`` will parse (basic form ``20260215``, week dates
    ``2026-W01-1``); parsing then rejects shape-valid but calendar-invalid values
    such as ``2026-02-30``, which DuckDB raises a ConversionException on.
    """
    if value is None:
        return None
    if _ISO_DATE_RE.match(value):
        try:
            date.fromisoformat(value)
        except ValueError:
            pass
        else:
            return value
    logger.warning("Invalid date value %r for DATE column; coercing to None", value)
    return None
