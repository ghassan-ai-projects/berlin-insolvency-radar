"""Domain validation utilities."""

import logging
import re

logger = logging.getLogger(__name__)

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_date_field(value: str | None) -> str | None:
    """Validate a string is a proper ISO date before passing to DuckDB DATE column."""
    if value is None:
        return None
    if _ISO_DATE_RE.match(value):
        return value
    logger.warning("Invalid date value %r for DATE column; coercing to None", value)
    return None
