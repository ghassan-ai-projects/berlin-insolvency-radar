"""Phase 1 Acceptance Tests for Legacy Import, Review, and Draft-Ready Core."""

import sys
import tempfile
from pathlib import Path

# Add root dir to path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from biradar.mcp.server import call_radar_tool
from biradar.services.container import AppContainer
from biradar.services.import_legacy import LegacyImportInput
from biradar.storage.db import compute_content_hash
from biradar.storage.repository import CandidateRepository, ScoreRepository
from tests.fixtures.phase1.build_legacy_fixture import build_legacy_fixture


@pytest.fixture
def temp_db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "radar_test.duckdb"


@pytest.fixture
def config_dir():
    return Path(__file__).parent.parent.parent / "config"


@pytest.fixture
def container(temp_db_path, config_dir):
    container = AppContainer(config_dir, temp_db_path)
    yield container
    container.close()


@pytest.fixture
def fixture_db_path():
    """Provide a temporary fixture DB for import tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "legacy_fixture.duckdb"
        base_dir = Path(__file__).parent.parent / "fixtures" / "phase1"
        build_legacy_fixture(str(base_dir / "fixture_rows.json"), str(fixture_path))
        yield fixture_path


def test_at_1_0_and_1_1_legacy_production_db_never_mutated_dry_run(
    container, fixture_db_path
):
    """AT-1.0 & AT-1.1: Legacy DB is never mutated, dry run writes nothing."""
    # Record pre-import state
    pre_stat = fixture_db_path.stat()
    pre_hash = compute_content_hash(fixture_db_path.read_bytes())

    params = LegacyImportInput(
        legacy_db_path=str(fixture_db_path),
        actor="test_user",
    )
    assert params.dry_run is True
    result = container.legacy_import.import_legacy_scout(params)

    assert result.ok is True
    assert result.data["dry_run"] is True
    assert result.data["raw_records_seen"] == 8
    assert result.data["distinct_candidates"] == 5
    assert result.data["duplicates"] == 1
    assert result.data["rejected"] == 2  # e.K. and Unknown Entity
    assert result.audit_id is None

    # Verify DB was not touched
    post_stat = fixture_db_path.stat()
    post_hash = compute_content_hash(fixture_db_path.read_bytes())
    assert post_stat.st_size == pre_stat.st_size
    assert post_stat.st_mtime == pre_stat.st_mtime
    assert post_hash == pre_hash

    # Verify nothing was written to repo DB
    for table in ["source_runs", "raw_records", "candidates", "evidence_items"]:
        row_count = container.db.conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        assert row_count == 0

    audit_count = container.db.conn.execute(
        "SELECT COUNT(*) FROM audit_events WHERE action = 'legacy_import_dry_run'"
    ).fetchone()[0]
    assert audit_count == 0


def test_at_1_2_real_import_is_idempotent(container, fixture_db_path):
    """AT-1.2: Real import is idempotent."""
    # First import
    params1 = LegacyImportInput(
        legacy_db_path=str(fixture_db_path),
        dry_run=False,
        actor="test_user",
    )
    result1 = container.legacy_import.import_legacy_scout(params1)
    assert result1.ok is True
    assert result1.data["distinct_candidates"] == 5  # 2 rejected, 1 duplicate
    assert result1.data["duplicates"] == 1
    assert any(
        "Malformed row LEG-008" in warning for warning in result1.data["warnings"]
    )

    # Second import - all should be recognized as duplicates
    result2 = container.legacy_import.import_legacy_scout(params1)
    assert result2.ok is True
    assert result2.data["distinct_candidates"] == 0  # All are duplicates now
    assert result2.data["duplicates"] == 6  # 5 unique + 1 intra-run duplicate
    assert result2.data["rejected"] == 2  # e.K. and Unknown Entity still rejected

    # Verify candidate count is exactly 5 (no duplicates created)
    candidate_count = container.db.conn.execute(
        "SELECT COUNT(*) FROM candidates"
    ).fetchone()[0]
    assert candidate_count == 5

    raw_count = container.db.conn.execute(
        "SELECT COUNT(*) FROM raw_records"
    ).fetchone()[0]
    assert raw_count == 6

    source_link_count = container.db.conn.execute(
        "SELECT COUNT(*) FROM candidate_sources"
    ).fetchone()[0]
    assert source_link_count == 6


def test_at_1_2_failed_real_import_rolls_back_partial_writes(
    container, fixture_db_path, monkeypatch
):
    """AT-1.2: A failed real import leaves no partial candidate data behind."""

    def fail_insert_evidence(*args, **kwargs):
        raise RuntimeError("forced evidence failure")

    monkeypatch.setattr(
        container.legacy_import.evidence_repo,
        "insert_evidence",
        fail_insert_evidence,
    )

    params = LegacyImportInput(
        legacy_db_path=str(fixture_db_path),
        dry_run=False,
        actor="test_user",
    )
    result = container.legacy_import.import_legacy_scout(params)

    assert result.ok is False
    assert result.errors[0]["code"] == "IMPORT_FAILED"
    assert result.audit_id is not None

    for table in ["raw_records", "candidates", "candidate_sources", "evidence_items"]:
        row_count = container.db.conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        assert row_count == 0

    failed_runs = container.db.conn.execute(
        "SELECT COUNT(*) FROM source_runs WHERE status = 'failed'"
    ).fetchone()[0]
    assert failed_runs == 1


def test_at_1_3_corporate_filter_allows_only_supported_forms(
    container, fixture_db_path
):
    """AT-1.3: Corporate filter allows only supported company forms."""
    params = LegacyImportInput(
        legacy_db_path=str(fixture_db_path),
        dry_run=False,
        actor="test_user",
    )
    result = container.legacy_import.import_legacy_scout(params)

    # Check that compliance filter rejected the e.K. and Unknown Entity (2 records)
    assert result.ok is True
    assert result.data["rejected"] == 2
    assert any(
        "Malformed row LEG-008" in warning for warning in result.data["warnings"]
    )

    # Check statuses of imported candidates (only allowed ones)
    statuses = container.db.conn.execute("SELECT status FROM candidates").fetchall()
    status_list = [row[0] for row in statuses]

    # Verify no publish_ready candidates exist yet (none approved)
    assert "publish_ready" not in status_list
    assert "needs_review" in status_list


def test_at_1_4_candidate_list_defaults_to_agent_work_queue(container):
    """AT-1.4: Candidate list defaults to agent work queue."""
    # First import some data
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "legacy_fixture.duckdb"
        base_dir = Path(__file__).parent.parent / "fixtures" / "phase1"
        build_legacy_fixture(str(base_dir / "fixture_rows.json"), str(fixture_path))
        params = LegacyImportInput(
            legacy_db_path=str(fixture_path), dry_run=False, actor="test"
        )
        container.legacy_import.import_legacy_scout(params)

    result = call_radar_tool(container, "radar_list_candidates", {})
    assert result.ok is True
    candidates = result.data
    assert len(candidates) > 0

    # Check that they have the required work queue fields
    for c in candidates:
        assert "candidate_id" in c
        assert "status" in c
        assert "next_action" in c
        assert "evidence_count" in c
        assert "score_status" in c


def test_at_1_5_candidate_detail_shows_evidence_and_lineage(container):
    """AT-1.5: Candidate detail shows evidence and lineage."""
    # Import data first
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "legacy_fixture.duckdb"
        base_dir = Path(__file__).parent.parent / "fixtures" / "phase1"
        build_legacy_fixture(str(base_dir / "fixture_rows.json"), str(fixture_path))
        params = LegacyImportInput(
            legacy_db_path=str(fixture_path), dry_run=False, actor="test"
        )
        container.legacy_import.import_legacy_scout(params)

    # Get a candidate ID
    candidate_id = container.db.conn.execute(
        "SELECT candidate_id FROM candidates LIMIT 1"
    ).fetchone()[0]

    result = call_radar_tool(
        container, "radar_get_candidate", {"candidate_id": candidate_id}
    )
    assert result.ok is True
    data = result.data

    assert "candidate" in data
    assert "evidence" in data
    assert len(data["evidence"]) > 0
    assert "source_lineage" in data
    assert len(data["source_lineage"]) > 0
    assert "audit_events" in data


def test_at_1_6_and_1_7_review_approves_candidate_and_score_or_rejects(container):
    """AT-1.6 & AT-1.7: Review approves/rejects candidate and computes deterministic score."""
    # Import data
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "legacy_fixture.duckdb"
        base_dir = Path(__file__).parent.parent / "fixtures" / "phase1"
        build_legacy_fixture(str(base_dir / "fixture_rows.json"), str(fixture_path))
        params = LegacyImportInput(
            legacy_db_path=str(fixture_path), dry_run=False, actor="test"
        )
        container.legacy_import.import_legacy_scout(params)

    candidate_id = container.db.conn.execute(
        "SELECT candidate_id FROM candidates WHERE status = 'review_ready' LIMIT 1"
    ).fetchone()[0]

    # Approve with score
    score_input = {
        "company_value": 3,
        "asset_quality": 4,
        "sector_attractiveness": 4,
        "speed_of_action": 3,
        "legal_risk": 2,
        "rationale": {"company_value": "Mid-sized tech firm"},
    }

    result = call_radar_tool(
        container,
        "radar_review_candidate",
        {
            "candidate_id": candidate_id,
            "decision": "approve",
            "reviewer": "test_reviewer",
            "note": "Looks good",
            "score_input": score_input,
        },
    )
    assert result.ok is True
    assert result.data["status"] == "publish_ready"
    assert result.data["computed_score"] is not None
    assert result.audit_id is not None

    # Verify DB state
    status = container.db.conn.execute(
        "SELECT status FROM candidates WHERE candidate_id = ?", [candidate_id]
    ).fetchone()[0]
    assert status == "publish_ready"

    score_count = container.db.conn.execute(
        "SELECT COUNT(*) FROM scores WHERE candidate_id = ? AND status = 'approved'",
        [candidate_id],
    ).fetchone()[0]
    assert score_count == 1

    # Reject without a note must be blocked and audited.
    other_candidate_id = container.db.conn.execute(
        "SELECT candidate_id FROM candidates WHERE status = 'review_ready' AND candidate_id != ? LIMIT 1",
        [candidate_id],
    ).fetchone()[0]
    result_reject_without_note = call_radar_tool(
        container,
        "radar_review_candidate",
        {
            "candidate_id": other_candidate_id,
            "decision": "reject",
            "reviewer": "test_reviewer",
        },
    )
    assert result_reject_without_note.ok is False
    assert result_reject_without_note.errors[0]["code"] == "NOTE_REQUIRED"
    assert result_reject_without_note.audit_id is not None

    # Reject with a note should persist the rejection and not create a score.
    result_reject = call_radar_tool(
        container,
        "radar_review_candidate",
        {
            "candidate_id": other_candidate_id,
            "decision": "reject",
            "reviewer": "test_reviewer",
            "note": "Consumer-style or out of editorial scope.",
        },
    )
    assert result_reject.ok is True
    assert result_reject.data["status"] == "rejected"
    rejected_score_count = container.db.conn.execute(
        "SELECT COUNT(*) FROM scores WHERE candidate_id = ?",
        [other_candidate_id],
    ).fetchone()[0]
    assert rejected_score_count == 0


def test_at_1_8_invalid_status_transitions_are_blocked(container):
    """AT-1.8: Invalid status transitions are blocked."""
    # Import data
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "legacy_fixture.duckdb"
        base_dir = Path(__file__).parent.parent / "fixtures" / "phase1"
        build_legacy_fixture(str(base_dir / "fixture_rows.json"), str(fixture_path))
        params = LegacyImportInput(
            legacy_db_path=str(fixture_path), dry_run=False, actor="test"
        )
        container.legacy_import.import_legacy_scout(params)

    candidate_id = container.db.conn.execute(
        "SELECT candidate_id FROM candidates WHERE status = 'review_ready' LIMIT 1"
    ).fetchone()[0]

    # Try to approve without score (should fail and audit without status change).
    result = call_radar_tool(
        container,
        "radar_review_candidate",
        {
            "candidate_id": candidate_id,
            "decision": "approve",
            "reviewer": "test_reviewer",
        },
    )
    assert result.ok is False
    assert any("MISSING_SCORE" in err["code"] for err in result.errors)
    assert result.audit_id is not None
    status = container.db.conn.execute(
        "SELECT status FROM candidates WHERE candidate_id = ?", [candidate_id]
    ).fetchone()[0]
    assert status == "review_ready"

    # Move a candidate to needs_more_info from review_ready.
    info_result = call_radar_tool(
        container,
        "radar_review_candidate",
        {
            "candidate_id": candidate_id,
            "decision": "needs_more_info",
            "reviewer": "test_reviewer",
        },
    )
    assert info_result.ok is True
    assert info_result.data["status"] == "needs_review"

    # Invalid transition is blocked and audited.
    invalid_result = call_radar_tool(
        container,
        "radar_review_candidate",
        {
            "candidate_id": candidate_id,
            "decision": "approve",
            "reviewer": "test_reviewer",
            "score_input": {
                "company_value": 3,
                "asset_quality": 3,
                "sector_attractiveness": 3,
                "speed_of_action": 3,
                "legal_risk": 3,
                "rationale": {},
            },
        },
    )
    assert invalid_result.ok is False
    assert invalid_result.errors[0]["code"] == "INVALID_TRANSITION"
    assert invalid_result.audit_id is not None


def test_at_1_9_issue_draft_uses_only_approved_candidates(container):
    """AT-1.9: Issue draft uses only approved candidates."""
    # Import and approve a candidate
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "legacy_fixture.duckdb"
        base_dir = Path(__file__).parent.parent / "fixtures" / "phase1"
        build_legacy_fixture(str(base_dir / "fixture_rows.json"), str(fixture_path))
        params = LegacyImportInput(
            legacy_db_path=str(fixture_path), dry_run=False, actor="test"
        )
        container.legacy_import.import_legacy_scout(params)

    candidate_id = container.db.conn.execute(
        "SELECT candidate_id FROM candidates WHERE status = 'review_ready' LIMIT 1"
    ).fetchone()[0]

    # Approve
    call_radar_tool(
        container,
        "radar_review_candidate",
        {
            "candidate_id": candidate_id,
            "decision": "approve",
            "reviewer": "test_reviewer",
            "score_input": {
                "company_value": 3,
                "asset_quality": 3,
                "sector_attractiveness": 3,
                "speed_of_action": 3,
                "legal_risk": 3,
                "rationale": {},
            },
        },
    )

    # Add an approved candidate with no evidence; it must be skipped.
    candidate_repo = CandidateRepository(container.db)
    score_repo = ScoreRepository(container.db)
    no_evidence_id = "cand_no_evidence"
    candidate_repo.upsert_candidate(
        candidate_id=no_evidence_id,
        company_name="No Evidence GmbH",
        legal_form="GmbH",
        court="Charlottenburg (Berlin)",
        case_number="99 IN 1/26",
        register_number="HRB 999999 B",
        publication_date="2026-06-15",
        publication_type="eroeffnung",
        status="publish_ready",
        source_quality="C",
    )
    score_repo.insert_score(
        score_id="score_no_evidence",
        candidate_id=no_evidence_id,
        score_version="v1",
        company_value=3,
        asset_quality=3,
        sector_attractiveness=3,
        speed_of_action=3,
        legal_risk=3,
        computed_score=2.4,
        category="interesting",
        rationale_json="{}",
        status="approved",
        reviewer="test_reviewer",
    )

    # Try to draft with an unapproved and no-evidence candidate (both skipped).
    fake_id = "cand_fake"
    result = call_radar_tool(
        container,
        "radar_create_issue_draft",
        {
            "week": "2026-W25",
            "tier": "free",
            "candidate_ids": [fake_id, no_evidence_id, candidate_id],
            "title": "Test Issue",
            "actor": "test_user",
        },
    )
    assert result.ok is True
    assert len(result.warnings) > 1
    assert any("no evidence" in warning for warning in result.warnings)
    assert result.data["candidate_count"] == 1

    no_valid_result = call_radar_tool(
        container,
        "radar_create_issue_draft",
        {
            "week": "2026-W25",
            "tier": "free",
            "candidate_ids": [no_evidence_id],
            "title": "No Evidence Issue",
            "actor": "test_user",
        },
    )
    assert no_valid_result.ok is False
    assert no_valid_result.errors[0]["code"] == "NO_VALID_CANDIDATES"
    assert no_valid_result.audit_id is not None


def test_at_1_10_export_writes_local_markdown_only(container):
    """AT-1.10: Export writes local Markdown only."""
    # Create an issue draft first
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "legacy_fixture.duckdb"
        base_dir = Path(__file__).parent.parent / "fixtures" / "phase1"
        build_legacy_fixture(str(base_dir / "fixture_rows.json"), str(fixture_path))
        params = LegacyImportInput(
            legacy_db_path=str(fixture_path), dry_run=False, actor="test"
        )
        container.legacy_import.import_legacy_scout(params)

    candidate_id = container.db.conn.execute(
        "SELECT candidate_id FROM candidates WHERE status = 'review_ready' LIMIT 1"
    ).fetchone()[0]

    call_radar_tool(
        container,
        "radar_review_candidate",
        {
            "candidate_id": candidate_id,
            "decision": "approve",
            "reviewer": "test_reviewer",
            "score_input": {
                "company_value": 3,
                "asset_quality": 3,
                "sector_attractiveness": 3,
                "speed_of_action": 3,
                "legal_risk": 3,
                "rationale": {},
            },
        },
    )

    draft_result = call_radar_tool(
        container,
        "radar_create_issue_draft",
        {
            "week": "2026-W25",
            "tier": "free",
            "candidate_ids": [candidate_id],
            "title": "Test Issue",
            "actor": "test_user",
        },
    )
    issue_id = draft_result.data["issue_id"]

    # Export
    result = call_radar_tool(
        container,
        "radar_export_issue",
        {
            "issue_id": issue_id,
            "format": "markdown",
            "actor": "test_user",
        },
    )
    assert result.ok is True
    assert "path" in result.data
    assert result.data["path"].endswith(".md")
    assert Path(result.data["path"]).exists()
    assert "beehiiv" not in result.next_action.lower()

    second_export = call_radar_tool(
        container,
        "radar_export_issue",
        {
            "issue_id": issue_id,
            "format": "markdown",
            "actor": "test_user",
        },
    )
    assert second_export.ok is False
    assert second_export.errors[0]["code"] == "INVALID_STATUS"
    assert second_export.audit_id is not None


def test_at_1_11_audit_trail_explains_candidate_history(container):
    """AT-1.11: Audit trail explains candidate history."""
    # Import and approve
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "legacy_fixture.duckdb"
        base_dir = Path(__file__).parent.parent / "fixtures" / "phase1"
        build_legacy_fixture(str(base_dir / "fixture_rows.json"), str(fixture_path))
        params = LegacyImportInput(
            legacy_db_path=str(fixture_path), dry_run=False, actor="test"
        )
        container.legacy_import.import_legacy_scout(params)

    candidate_id = container.db.conn.execute(
        "SELECT candidate_id FROM candidates WHERE status = 'review_ready' LIMIT 1"
    ).fetchone()[0]

    call_radar_tool(
        container,
        "radar_review_candidate",
        {
            "candidate_id": candidate_id,
            "decision": "approve",
            "reviewer": "test_reviewer",
            "score_input": {
                "company_value": 3,
                "asset_quality": 3,
                "sector_attractiveness": 3,
                "speed_of_action": 3,
                "legal_risk": 3,
                "rationale": {},
            },
        },
    )

    result = call_radar_tool(
        container,
        "radar_audit_trail",
        {
            "entity_type": "candidate",
            "entity_id": candidate_id,
        },
    )
    assert result.ok is True
    assert len(result.data) >= 1  # At least the review event
    actions = [event["action"] for event in result.data]
    assert "candidate_reviewed" in actions


def test_at_1_12_health_reports_real_work_remaining(container):
    """AT-1.12: Health reports real work remaining."""
    # Import data
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "legacy_fixture.duckdb"
        base_dir = Path(__file__).parent.parent / "fixtures" / "phase1"
        build_legacy_fixture(str(base_dir / "fixture_rows.json"), str(fixture_path))
        params = LegacyImportInput(
            legacy_db_path=str(fixture_path), dry_run=False, actor="test"
        )
        container.legacy_import.import_legacy_scout(params)

    result = call_radar_tool(container, "radar_health", {})
    assert result.ok is True

    # Should have counts now
    assert "counts" in result.data
    # Should have next action
    assert "next_action" in result.data
    next_action_lower = result.data["next_action"].lower()
    assert (
        "review" in next_action_lower
        or "import" in next_action_lower
        or "approve" in next_action_lower
        or "score" in next_action_lower
    )
