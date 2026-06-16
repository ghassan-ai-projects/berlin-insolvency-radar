"""CLI entrypoint for biradar."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from biradar.config.settings import load_config
from biradar.mcp.server import create_mcp_server, list_radar_tools
from biradar.services.pipeline import run_pipeline, run_pipeline_check

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Load .env so that downstream agents (extraction, risk_review)
# see DEEPSEEK_API_KEY when they read os.environ at call time.
_dotenv_path = PROJECT_ROOT / ".env"
if _dotenv_path.exists():
    load_dotenv(_dotenv_path)

DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "radar.duckdb"

# Load .env if present
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _key, _val = _line.split("=", 1)
        _key = _key.strip()
        _val = _val.strip().strip("\"'").strip()
        os.environ.setdefault(_key, _val)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="biradar")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help="Path to the configuration directory.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the DuckDB radar database.",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("check", help="Load config and validate startup settings.")
    subparsers.add_parser(
        "mcp-info", help="Validate MCP server construction and list tools."
    )
    subparsers.add_parser("serve-mcp", help="Run the MCP server over stdio.")
    subparsers.add_parser("serve", help="Alias for serve-mcp.")

    pipeline_parser = subparsers.add_parser(
        "pipeline-run", help="Execute the production workflow pipeline."
    )
    pipeline_parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="Start date for scraping (YYYY-MM-DD)",
    )
    pipeline_parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        help="End date for scraping (YYYY-MM-DD)",
    )
    pipeline_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="If set, do not persist records to the database.",
    )
    pipeline_parser.add_argument(
        "--thread-id",
        type=str,
        default="pipeline_default",
        help="LangGraph thread ID for checkpointing and resume.",
    )
    subparsers.add_parser(
        "pipeline-check",
        help="Run fixture-backed validation with deterministic stubs against a temporary DuckDB.",
    )

    return parser


def main() -> None:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "check"

    try:
        if command == "check":
            config = load_config(args.config_dir)
            print(f"Loaded config for biradar {config.scoring.version}")
            return

        if command == "mcp-info":
            create_mcp_server(args.config_dir, args.db_path)
            tools = list_radar_tools()
            print(f"MCP server initialized with {len(tools)} tools:")
            for tool in tools:
                print(f"- {tool.name}")
            return

        if command in {"serve-mcp", "serve"}:
            asyncio.run(run_mcp_server(args.config_dir, args.db_path))
            return

        if command == "pipeline-run":
            from datetime import date

            start_date = date.fromisoformat(args.start_date)
            end_date = date.fromisoformat(args.end_date)

            print(
                f"Starting pipeline: {start_date} to {end_date} (dry_run={args.dry_run})"
            )
            result = run_pipeline(
                start_date=start_date,
                end_date=end_date,
                dry_run=args.dry_run,
                thread_id=args.thread_id,
            )

            if result["status"] == "success":
                print("Pipeline completed successfully.")
                if result.get("export_path"):
                    print(f"Export path: {result['export_path']}")
                if result.get("warnings"):
                    print(f"Warnings: {result['warnings']}")
            else:
                print(f"Pipeline failed: {result.get('error')}")
                sys.exit(1)
            return

        if command == "pipeline-check":
            result = run_pipeline_check()
            if result["status"] != "success":
                print(f"Pipeline check failed: {result}")
                sys.exit(1)
            print("Pipeline check passed.")
            print(result)
            return

    except Exception as e:
        print(f"Startup error: {e}", file=sys.stderr)
        sys.exit(1)


async def run_mcp_server(config_dir: Path, db_path: Path) -> None:
    """Run the MCP server over stdio."""
    from mcp.server.stdio import stdio_server

    server = create_mcp_server(config_dir, db_path)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    main()
