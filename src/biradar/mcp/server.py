"""MCP Server for Berlin Insolvency Radar."""

import json
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool
from pydantic import ValidationError

from biradar.mcp.envelope import ResultEnvelope
from biradar.services.container import AppContainer
from biradar.services.import_legacy import LegacyImportInput


def list_radar_tools() -> list[Tool]:
    """Return the v0 MCP tool definitions."""
    return [
        Tool(
            name="radar_health",
            description="Check application health, database status, and next recommended action.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="radar_import_legacy_scout",
            description="Import or dry-run import from legacy insolvency_scout DuckDB.",
            inputSchema={
                "type": "object",
                "properties": {
                    "legacy_db_path": {"type": "string"},
                    "since": {"type": "string", "description": "YYYY-MM-DD"},
                    "until": {"type": "string", "description": "YYYY-MM-DD"},
                    "dry_run": {"type": "boolean", "default": True},
                    "actor": {"type": "string", "default": "system"},
                },
                "required": ["legacy_db_path"],
            },
        ),
        Tool(
            name="radar_list_candidates",
            description="List candidates, defaulting to those needing work.",
            inputSchema={
                "type": "object",
                "properties": {
                    "statuses": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "default": 25},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        ),
        Tool(
            name="radar_get_candidate",
            description="Get full candidate detail with evidence and lineage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string"},
                },
                "required": ["candidate_id"],
            },
        ),
        Tool(
            name="radar_review_candidate",
            description="Review a candidate: approve, reject, needs_more_info, mark_duplicate, or archive.",
            inputSchema={
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string"},
                    "decision": {
                        "type": "string",
                        "enum": [
                            "approve",
                            "reject",
                            "needs_more_info",
                            "mark_duplicate",
                            "archive",
                        ],
                    },
                    "reviewer": {"type": "string"},
                    "note": {"type": "string"},
                    "score_input": {
                        "type": "object",
                        "properties": {
                            "company_value": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "asset_quality": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "sector_attractiveness": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "speed_of_action": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "legal_risk": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "rationale": {
                                "type": "object",
                                "additionalProperties": {"type": "string"},
                            },
                        },
                        "required": [
                            "company_value",
                            "asset_quality",
                            "sector_attractiveness",
                            "speed_of_action",
                            "legal_risk",
                        ],
                    },
                },
                "required": ["candidate_id", "decision", "reviewer"],
            },
        ),
        Tool(
            name="radar_create_issue_draft",
            description="Create a newsletter issue draft from approved candidates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "week": {"type": "string"},
                    "tier": {"type": "string", "enum": ["free", "paid"]},
                    "candidate_ids": {"type": "array", "items": {"type": "string"}},
                    "title": {"type": "string"},
                    "include_disclaimer": {"type": "boolean", "default": True},
                    "actor": {"type": "string", "default": "system"},
                },
                "required": ["week", "tier", "candidate_ids", "title"],
            },
        ),
        Tool(
            name="radar_export_issue",
            description="Export an issue draft to a local Markdown file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "format": {"type": "string", "default": "markdown"},
                    "actor": {"type": "string", "default": "system"},
                },
                "required": ["issue_id"],
            },
        ),
        Tool(
            name="radar_audit_trail",
            description="Retrieve audit events for an entity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string"},
                    "entity_id": {"type": "string"},
                    "actor": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        ),
    ]


def call_radar_tool(
    container: AppContainer, name: str, arguments: dict[str, Any] | None = None
) -> ResultEnvelope[Any]:
    """Execute a v0 radar tool through the same path used by MCP."""
    args = arguments or {}
    try:
        if name == "radar_health":
            return container.health.check()
        if name == "radar_import_legacy_scout":
            params = LegacyImportInput(**args)
            return container.legacy_import.import_legacy_scout(
                params, actor=args.get("actor", "system")
            )
        if name == "radar_list_candidates":
            return container.candidates.list_candidates(
                statuses=args.get("statuses"),
                limit=args.get("limit", 25),
                offset=args.get("offset", 0),
            )
        if name == "radar_get_candidate":
            if "candidate_id" not in args:
                return validation_error("candidate_id is required.")
            return container.candidates.get_candidate(args["candidate_id"])
        if name == "radar_review_candidate":
            missing = [
                field
                for field in ("candidate_id", "decision", "reviewer")
                if field not in args
            ]
            if missing:
                return validation_error(
                    f"Missing required fields: {', '.join(missing)}."
                )
            return container.reviews.review_candidate(
                candidate_id=args["candidate_id"],
                decision=args["decision"],
                reviewer=args["reviewer"],
                note=args.get("note"),
                score_input=args.get("score_input"),
            )
        if name == "radar_create_issue_draft":
            missing = [
                field
                for field in ("week", "tier", "candidate_ids", "title")
                if field not in args
            ]
            if missing:
                return validation_error(
                    f"Missing required fields: {', '.join(missing)}."
                )
            return container.issues.create_issue_draft(
                week=args["week"],
                tier=args["tier"],
                candidate_ids=args["candidate_ids"],
                title=args["title"],
                include_disclaimer=args.get("include_disclaimer", True),
                actor=args.get("actor", "system"),
            )
        if name == "radar_export_issue":
            if "issue_id" not in args:
                return validation_error("issue_id is required.")
            return container.issues.export_issue(
                issue_id=args["issue_id"],
                format=args.get("format", "markdown"),
                actor=args.get("actor", "system"),
            )
        if name == "radar_audit_trail":
            events = container.audit_repo.get_events(
                entity_type=args.get("entity_type"),
                entity_id=args.get("entity_id"),
                actor=args.get("actor"),
                limit=args.get("limit", 50),
            )
            return ResultEnvelope(ok=True, data=events)
        return ResultEnvelope(
            ok=False,
            errors=[
                {
                    "code": "TOOL_NOT_FOUND",
                    "message": f"Unknown tool: {name}",
                    "retryable": False,
                }
            ],
        )
    except ValidationError as e:
        return validation_error(str(e))
    except Exception as e:
        return ResultEnvelope(
            ok=False,
            errors=[{"code": "INTERNAL_ERROR", "message": str(e), "retryable": True}],
        )


def validation_error(message: str) -> ResultEnvelope[Any]:
    """Build a stable validation failure envelope."""
    return ResultEnvelope(
        ok=False,
        errors=[
            {
                "code": "VALIDATION_ERROR",
                "message": message,
                "retryable": False,
                "next_action": "Fix the tool arguments and retry.",
            }
        ],
        next_action="Fix the tool arguments and retry.",
    )


def create_mcp_server(config_dir: Path, db_path: Path) -> Server:
    """Create and configure the MCP server."""
    server = Server("biradar")
    container = AppContainer(config_dir, db_path)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return list_radar_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        result = call_radar_tool(container, name, arguments)
        return [
            TextContent(
                type="text",
                text=json.dumps(result.model_dump(), indent=2, default=str),
            )
        ]

    return server
