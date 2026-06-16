"""Pydantic input models for MCP v0 tools."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

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
    "ListSourceRunsInput",
    "ReviewCandidateInput",
    "RunPhase2WorkflowInput",
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


class ListSourceRunsInput(BaseModel):
    source_id: str | None = None
    status: str | None = None
    limit: int = Field(default=20, ge=1, le=200)


class RunPhase2WorkflowInput(BaseModel):
    start_date: date = Field(description="Start date for scraping (YYYY-MM-DD)")
    end_date: date = Field(description="End date for scraping (YYYY-MM-DD)")
    dry_run: bool = False

    @model_validator(mode="after")
    def validate_date_order(self) -> "RunPhase2WorkflowInput":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self
