"""Pydantic input models for MCP v0 tools."""

from typing import Literal

from pydantic import BaseModel, Field

from biradar.domain.scoring import ScoreInput

# Re-export LegacyImportInput to keep things unified
from biradar.services.import_legacy import LegacyImportInput as ImportLegacyScoutInput

__all__ = [
    "AuditTrailInput",
    "CreateIssueDraftInput",
    "ExportIssueInput",
    "GetCandidateInput",
    "HealthInput",
    "ImportLegacyScoutInput",
    "ListCandidatesInput",
    "ReviewCandidateInput",
]


class HealthInput(BaseModel):
    """Input for radar_health."""

    pass


class ListCandidatesInput(BaseModel):
    statuses: (
        list[
            Literal[
                "raw_candidate",
                "deduped_candidate",
                "needs_review",
                "review_ready",
                "publish_ready",
                "rejected",
                "archived",
                "duplicate",
                "quarantined",
            ]
        ]
        | None
    ) = None
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class GetCandidateInput(BaseModel):
    candidate_id: str


class ReviewCandidateInput(BaseModel):
    candidate_id: str
    decision: Literal[
        "approve", "reject", "needs_more_info", "mark_duplicate", "archive"
    ]
    reviewer: str
    note: str | None = None
    score_input: ScoreInput | None = None


class CreateIssueDraftInput(BaseModel):
    week: str
    tier: Literal["free", "paid"]
    candidate_ids: list[str]
    title: str
    include_disclaimer: bool = True
    actor: str = "system"


class ExportIssueInput(BaseModel):
    issue_id: str
    format: Literal["markdown"] = "markdown"
    actor: str = "system"


class AuditTrailInput(BaseModel):
    entity_type: str | None = None
    entity_id: str | None = None
    actor: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
