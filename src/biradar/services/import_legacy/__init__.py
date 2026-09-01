"""Legacy import service for reading insolvency-scout DuckDB safely.

The public surface is re-exported so consumers keep importing from
``biradar.services.import_legacy``. Tests patch repositories on the service
instance (``container.legacy_import.evidence_repo``), so no module-level
monkeypatch anchors are needed here.
"""

from biradar.services.import_legacy.models import LegacyImportInput
from biradar.services.import_legacy.runner import LegacyImportService

__all__ = ["LegacyImportInput", "LegacyImportService"]
