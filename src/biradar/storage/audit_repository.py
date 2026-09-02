"""Audit event repository: append-only event writes and filtered reads."""

import json
import uuid
from typing import Any

from biradar.storage.base import BaseRepository
from biradar.storage.clock import utc_now_iso
from biradar.storage.rows import rows_as_dicts


def _event_filters(
    entity_type: str | None,
    entity_id: str | None,
    actor: str | None,
) -> tuple[str, list[Any]]:
    """Build the WHERE fragment and parameters for optional event filters."""
    fragment = ""
    params: list[Any] = []
    if entity_type:
        fragment += " AND entity_type = ?"
        params.append(entity_type)
    if entity_id:
        fragment += " AND entity_id = ?"
        params.append(entity_id)
    if actor:
        fragment += " AND actor = ?"
        params.append(actor)
    return fragment, params


class AuditRepository(BaseRepository):
    """Handles append-only audit event writes."""

    def log_event(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        request_data: dict[str, Any] | None = None,
        result_data: dict[str, Any] | None = None,
    ) -> str:
        """Log an audit event and return the audit_id."""
        audit_id = f"audit_{uuid.uuid4().hex}"
        request_json = json.dumps(request_data) if request_data else None
        result_json = json.dumps(result_data) if result_data else None

        self.db.conn.execute(
            """
            INSERT INTO audit_events
            (audit_id, actor, action, entity_type, entity_id, request_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                audit_id,
                actor,
                action,
                entity_type,
                entity_id,
                request_json,
                result_json,
                utc_now_iso(),
            ],
        )
        return audit_id

    def get_events(
        self,
        entity_type: str | None = None,
        entity_id: str | None = None,
        actor: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve audit events with optional filters."""
        filters, filter_params = _event_filters(entity_type, entity_id, actor)
        query = (
            "SELECT * FROM audit_events WHERE 1=1"
            f"{filters} ORDER BY created_at DESC LIMIT ?"
        )
        cursor = self.db.conn.execute(query, [*filter_params, limit])
        return rows_as_dicts(cursor)
