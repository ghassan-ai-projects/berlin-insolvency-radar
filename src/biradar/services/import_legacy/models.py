"""Input model for the legacy import service."""

from pydantic import BaseModel


class LegacyImportInput(BaseModel):
    legacy_db_path: str
    since: str | None = None
    until: str | None = None
    dry_run: bool = True
    actor: str = "system"
