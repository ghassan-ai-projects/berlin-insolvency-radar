"""Application service container for dependency injection."""

from pathlib import Path

from biradar.config.settings import load_config
from biradar.services.candidates import CandidateService
from biradar.services.health import HealthService
from biradar.services.import_legacy import LegacyImportService
from biradar.services.issues import IssueService
from biradar.services.reviews import ReviewService
from biradar.storage.db import Database
from biradar.storage.repository import AuditRepository


class AppContainer:
    """Singleton-like container for application services."""

    def __init__(self, config_dir: Path, db_path: Path):
        self.config = load_config(config_dir)
        self.db = Database(db_path)
        self.db.run_migrations()

        self.audit_repo = AuditRepository(self.db)

        self.health = HealthService(self.db, self.config)
        self.candidates = CandidateService(self.db)
        self.reviews = ReviewService(self.db, self.config)
        self.issues = IssueService(self.db, db_path.parent / "exports")
        self.legacy_import = LegacyImportService(self.db, self.config, self.audit_repo)

    def close(self):
        self.db.close()
