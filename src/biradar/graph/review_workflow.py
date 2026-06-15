"""Minimal LangGraph review workflow shell."""

from langgraph.graph import END, StateGraph

from biradar.graph.state import ReviewWorkflowState
from biradar.services.container import AppContainer


def validate_and_review_node(
    state: ReviewWorkflowState, container: AppContainer
) -> ReviewWorkflowState:
    """Validate inputs and execute the review via service layer."""
    try:
        result = container.reviews.review_candidate(
            candidate_id=state["candidate_id"],
            decision=state["decision"],
            reviewer=state["reviewer"],
            note=state.get("note"),
            score_input=state.get("score_input"),
        )

        if not result.ok:
            return {
                **state,
                "status": "failed",
                "error": result.errors[0]["message"]
                if result.errors
                else "Unknown error",
            }

        return {
            **state,
            "status": "success",
            "new_status": result.data["status"] if result.data else "unknown",
            "computed_score": result.data.get("computed_score")
            if result.data
            else None,  # type: ignore
        }
    except Exception as e:
        return {
            **state,
            "status": "failed",
            "error": str(e),
        }


def build_review_workflow(container: AppContainer):
    """Build and compile the review workflow graph."""
    workflow = StateGraph(ReviewWorkflowState)

    workflow.add_node(
        "review",
        lambda state: validate_and_review_node(state, container),  # type: ignore
    )

    workflow.set_entry_point("review")

    workflow.add_conditional_edges(
        "review",
        lambda state: "end" if state["status"] in ("success", "failed") else "review",
        {
            "end": END,
            "review": "review",  # Retry logic could go here
        },
    )

    return workflow.compile()  # type: ignore
