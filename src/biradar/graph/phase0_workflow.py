"""Auditable Phase 0 LangGraph health workflow."""

from typing import cast

from langgraph.graph import END, StateGraph

from biradar.graph.state import Phase0HealthWorkflowState
from biradar.services.container import AppContainer


def phase0_health_node(
    state: Phase0HealthWorkflowState, container: AppContainer
) -> Phase0HealthWorkflowState:
    """Run a safe health workflow and record its audit marker."""
    try:
        health = container.health.check()
        if not health.ok or not health.data:
            message = (
                health.errors[0]["message"]
                if health.errors
                else "Phase 0 health workflow failed."
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
            action="phase0_health_workflow_ran",
            entity_type="workflow",
            entity_id="phase0_health",
            request_data={"workflow": "phase0_health"},
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


def build_phase0_health_workflow(container: AppContainer):
    """Build the minimal Phase 0 workflow shell."""
    workflow = StateGraph(Phase0HealthWorkflowState)
    workflow.add_node(
        "phase0_health",
        lambda state: phase0_health_node(
            cast(Phase0HealthWorkflowState, state), container
        ),
    )
    workflow.set_entry_point("phase0_health")
    workflow.add_edge("phase0_health", END)
    return workflow.compile()
