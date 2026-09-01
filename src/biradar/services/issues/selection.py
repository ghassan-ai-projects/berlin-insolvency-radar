"""Publishable-candidate selection for issue drafts."""

from typing import Any

from biradar.storage.repository import (
    CandidateRepository,
    EvidenceRepository,
    ScoreRepository,
)


def _collect_publishable_candidates(
    candidate_repo: CandidateRepository,
    score_repo: ScoreRepository,
    evidence_repo: EvidenceRepository,
    candidate_ids: list[str],
    tier: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Gather scoreable, evidenced candidates, warning per skipped id."""
    candidates_data: list[dict[str, Any]] = []
    warnings: list[str] = []

    for cid in candidate_ids:
        candidate = candidate_repo.get_by_id(cid)
        if not candidate:
            warnings.append(f"Candidate {cid} not found, skipped.")
            continue

        if candidate["status"] != "publish_ready":
            warnings.append(
                f"Candidate {cid} is not publish_ready (status: {candidate['status']}), skipped."
            )
            continue

        score = score_repo.get_latest_approved_for_candidate(cid)
        if not score:
            warnings.append(f"Candidate {cid} has no approved score, skipped.")
            continue

        evidence = evidence_repo.get_for_candidate(cid)
        if not evidence:
            warnings.append(f"Candidate {cid} has no evidence, skipped.")
            continue

        filtered_evidence = _visible_evidence(evidence, tier)
        if not filtered_evidence:
            warnings.append(
                f"Candidate {cid} has no publishable evidence for {tier} tier, skipped."
            )
            continue

        candidates_data.append(
            {
                "candidate": candidate,
                "score": score,
                "evidence": filtered_evidence,
            }
        )

    return candidates_data, warnings


def _visible_evidence(
    evidence: list[dict[str, Any]], tier: str
) -> list[dict[str, Any]]:
    """Drop admin-contact evidence in the free tier."""
    return [
        ev for ev in evidence if not (tier == "free" and "admin" in ev["field"].lower())
    ]
