"""Auditable health workflow."""

from typing import cast

from langgraph.graph import END, StateGraph

from biradar.graph.state import HealthWorkflowState
from biradar.services.container import AppContainer


def health_node(
    state: HealthWorkflowState, container: AppContainer
) -> HealthWorkflowState:
    """Run a safe health workflow and record its audit marker."""
    try:
        health = container.health.check()
        if not health.ok or not health.data:
            message = (
                health.errors[0]["message"]
                if health.errors
                else "Health workflow failed."
            )
            return {**state, "status": "failed", "error": message}
        health_data = health.data

        candidate_row = container.db.conn.execute(
            "SELECT COUNT(*) FROM candidates"
        ).fetchone()
        source_run_row = container.db.conn.execute(
            "SELECT COUNT(*) FROM source_runs"
        ).fetchone()
        candidate_count = int(candidate_row[0]) if candidate_row else 0
        source_run_count = int(source_run_row[0]) if source_run_row else 0

        audit_id = container.audit_repo.log_event(
            actor=state.get("actor", "system"),
            action="health_workflow_ran",
            entity_type="workflow",
            entity_id="health_check",
            request_data={"workflow": "health_check"},
            result_data={
                "status": "success",
                "schema_version": health_data["database"]["schema_version"],
                "candidate_count": candidate_count,
                "source_run_count": source_run_count,
            },
        )

        return {
            **state,
            "status": "success",
            "database_connected": health_data["database"]["connected"],
            "database_path": health_data["database"]["path"],
            "schema_version": health_data["database"]["schema_version"],
            "candidate_count": candidate_count,
            "source_run_count": source_run_count,
            "audit_id": audit_id,
        }
    except Exception as e:
        return {**state, "status": "failed", "error": str(e)}


def build_health_workflow(container: AppContainer):
    """Build the minimal health workflow shell."""
    workflow = StateGraph(HealthWorkflowState)
    workflow.add_node(
        "health_check",
        lambda state: health_node(cast(HealthWorkflowState, state), container),
    )
    workflow.set_entry_point("health_check")
    workflow.add_edge("health_check", END)
    return workflow.compile()
