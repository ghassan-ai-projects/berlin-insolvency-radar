"""Repository layer for database operations. Centralizes all DuckDB access.

The repository classes live in per-concern modules inside ``biradar.storage``
and are re-exported here, so ``biradar.storage.repository`` stays the single
import surface for the service layer.
"""

import logging

from biradar.storage.audit_repository import AuditRepository
from biradar.storage.candidate_repository import CandidateRepository
from biradar.storage.enrichment_repository import (
    EnrichmentClaimRepository,
    EnrichmentRepository,
)
from biradar.storage.evidence_repository import EvidenceRepository
from biradar.storage.issue_repository import IssueRepository
from biradar.storage.raw_record_repository import RawRecordRepository
from biradar.storage.review_repository import ReviewRepository
from biradar.storage.score_repository import ScoreRepository
from biradar.storage.source_run_repository import SourceRunRepository

logger = logging.getLogger(__name__)

__all__ = [
    "AuditRepository",
    "CandidateRepository",
    "EnrichmentClaimRepository",
    "EnrichmentRepository",
    "EvidenceRepository",
    "IssueRepository",
    "RawRecordRepository",
    "ReviewRepository",
    "ScoreRepository",
    "SourceRunRepository",
]
