"""Unit tests for the CLI entrypoint: parser, command dispatch, and stdio server."""

import asyncio
import sys
from pathlib import Path

import pytest

from biradar.cli.main import build_parser, json_safe, main, run_mcp_server


@pytest.fixture
def argv(monkeypatch):
    """Point sys.argv at the given command words for parser.parse_args()."""

    def _set(*words):
        monkeypatch.setattr(sys, "argv", ["biradar", *words])

    return _set


class ScoringStub:
    version = "test-1.2.3"


class ConfigStub:
    scoring = ScoringStub()


class ToolStub:
    def __init__(self, name):
        self.name = name


def test_build_parser_defaults_to_check_command_paths(tmp_path):
    args = build_parser().parse_args([])

    assert args.command is None
    assert args.config_dir.name == "config"
    assert args.db_path.name == "radar.duckdb"


def test_build_parser_reads_pipeline_run_arguments():
    args = build_parser().parse_args(
        [
            "pipeline-run",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-01-31",
            "--dry-run",
            "--thread-id",
            "t1",
            "--max-records",
            "5",
        ]
    )

    assert args.command == "pipeline-run"
    assert args.start_date == "2026-01-01"
    assert args.end_date == "2026-01-31"
    assert args.dry_run is True
    assert args.thread_id == "t1"
    assert args.max_records == 5


def test_build_parser_pipeline_run_requires_both_dates():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["pipeline-run", "--start-date", "2026-01-01"])


@pytest.mark.parametrize(
    ("command", "default_max_records"),
    [
        ("live-smoke-portal", 10),
        ("live-smoke-stubbed", 10),
        ("live-smoke-full", 3),
    ],
)
def test_build_parser_live_smoke_commands_carry_date_and_cap_arguments(
    command, default_max_records
):
    args = build_parser().parse_args(
        [command, "--start-date", "2026-01-01", "--end-date", "2026-01-31"]
    )

    assert args.command == command
    assert args.max_records == default_max_records


def test_check_command_loads_config_and_reports_version(argv, monkeypatch, capsys):
    argv("check")
    seen = {}
    monkeypatch.setattr(
        "biradar.cli.main.load_config",
        lambda config_dir: (seen.setdefault("dir", config_dir), ConfigStub())[1],
    )

    main()

    out = capsys.readouterr().out
    assert seen["dir"].name == "config"
    assert "test-1.2.3" in out


def test_no_command_defaults_to_check(argv, monkeypatch):
    argv()
    monkeypatch.setattr(
        "biradar.cli.main.load_config", lambda _config_dir: ConfigStub()
    )

    main()


def test_mcp_info_lists_the_registered_tools(argv, monkeypatch, capsys):
    argv("mcp-info")
    monkeypatch.setattr(
        "biradar.cli.main.create_mcp_server",
        lambda _config_dir, _db_path: object(),
    )
    monkeypatch.setattr(
        "biradar.cli.main.list_radar_tools",
        lambda: [ToolStub("get_candidates"), ToolStub("health_check")],
    )

    main()

    out = capsys.readouterr().out
    assert "2 tools" in out
    assert "- get_candidates" in out
    assert "- health_check" in out


def test_serve_command_runs_the_mcp_server(argv, monkeypatch):
    argv("serve")
    calls = {}

    async def fake_run_mcp_server(config_dir, db_path):
        calls["paths"] = (config_dir, db_path)

    monkeypatch.setattr("biradar.cli.main.run_mcp_server", fake_run_mcp_server)

    main()

    assert calls["paths"][1].name == "radar.duckdb"


def test_pipeline_run_reports_success_with_export_path_and_warnings(
    argv, monkeypatch, capsys
):
    argv(
        "pipeline-run",
        "--start-date",
        "2026-01-01",
        "--end-date",
        "2026-01-31",
        "--dry-run",
    )
    seen = {}

    def fake_run_pipeline(**kwargs):
        seen.update(kwargs)
        return {
            "status": "success",
            "export_path": "out/issue.md",
            "warnings": ["stale evidence"],
        }

    monkeypatch.setattr("biradar.cli.main.run_pipeline", fake_run_pipeline)

    main()

    out = capsys.readouterr().out
    assert seen["dry_run"] is True
    assert seen["start_date"].isoformat() == "2026-01-01"
    assert "Pipeline completed successfully." in out
    assert "out/issue.md" in out
    assert "stale evidence" in out


def test_pipeline_run_exits_nonzero_when_the_pipeline_fails(argv, monkeypatch, capsys):
    argv("pipeline-run", "--start-date", "2026-01-01", "--end-date", "2026-01-31")
    monkeypatch.setattr(
        "biradar.cli.main.run_pipeline",
        lambda **_kwargs: {"status": "failed", "error": "portal unreachable"},
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1
    assert "portal unreachable" in capsys.readouterr().out


def test_pipeline_run_rejects_malformed_dates_with_a_startup_error(argv, capsys):
    argv("pipeline-run", "--start-date", "not-a-date", "--end-date", "2026-01-31")

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1
    assert "Startup error" in capsys.readouterr().err


def test_pipeline_check_prints_the_result_envelope(argv, monkeypatch, capsys):
    argv("pipeline-check")
    monkeypatch.setattr(
        "biradar.cli.main.run_pipeline_check",
        lambda: {"status": "success", "candidates": 2},
    )

    main()

    out = capsys.readouterr().out
    assert "Pipeline check passed." in out
    assert "candidates" in out


def test_pipeline_check_exits_nonzero_on_failure(argv, monkeypatch):
    argv("pipeline-check")
    monkeypatch.setattr(
        "biradar.cli.main.run_pipeline_check", lambda: {"status": "failed"}
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1


@pytest.mark.parametrize(
    ("command", "run_mode"),
    [
        ("live-smoke-portal", "portal_only"),
        ("live-smoke-stubbed", "portal_with_stubs"),
        ("live-smoke-full", "full_live"),
    ],
)
def test_live_smoke_commands_map_to_their_run_mode(
    argv, monkeypatch, command, run_mode
):
    argv(command, "--start-date", "2026-01-01", "--end-date", "2026-01-31")
    seen = {}
    monkeypatch.setattr(
        "biradar.cli.main.run_pipeline",
        lambda **kwargs: (seen.update(kwargs), {"status": "success"})[1],
    )

    main()

    assert seen["run_mode"] == run_mode
    assert seen["dry_run"] is False
    assert seen["thread_id"].startswith(command)


def test_live_smoke_command_exits_nonzero_when_the_pipeline_fails(argv, monkeypatch):
    argv("live-smoke-portal", "--start-date", "2026-01-01", "--end-date", "2026-01-31")
    monkeypatch.setattr(
        "biradar.cli.main.run_pipeline",
        lambda **_kwargs: {"status": "failed", "error": "blocked"},
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1


def test_json_safe_serializes_non_json_types():
    payload = {"path": Path("exports/issue.md"), "when": "2026-01-01"}

    rendered = json_safe(payload)

    assert "exports/issue.md" in rendered


def test_run_mcp_server_serves_the_server_over_stdio(monkeypatch, tmp_path):
    events = []

    class FakeServer:
        def create_initialization_options(self):
            return {"init": "options"}

        async def run(self, read_stream, write_stream, init_options):
            events.append((read_stream, write_stream, init_options))

    class FakeStdioServer:
        def __call__(self):
            return self

        async def __aenter__(self):
            return ("read", "write")

        async def __aexit__(self, *exc_info):
            return False

    monkeypatch.setattr("mcp.server.stdio.stdio_server", FakeStdioServer())
    monkeypatch.setattr(
        "biradar.cli.main.create_mcp_server",
        lambda _config_dir, _db_path: FakeServer(),
    )

    asyncio.run(run_mcp_server(tmp_path / "config", tmp_path / "radar.duckdb"))

    assert events == [("read", "write", {"init": "options"})]
