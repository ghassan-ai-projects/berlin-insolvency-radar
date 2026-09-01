"""Result container shared by the portal response parsers."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedPortalResponse:
    records: list[dict[str, Any]]
    parser_name: str
    error_code: str | None = None
