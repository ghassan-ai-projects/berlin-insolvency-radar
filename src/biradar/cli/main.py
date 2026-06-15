"""CLI entrypoint for biradar."""

import argparse
import asyncio
import sys
from pathlib import Path

from biradar.config.settings import load_config
from biradar.mcp.server import create_mcp_server, list_radar_tools

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "radar.duckdb"


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
    return parser


def main() -> None:
    """Main CLI entrypoint."""
    args = build_parser().parse_args()
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
        if command == "serve-mcp":
            asyncio.run(run_mcp_server(args.config_dir, args.db_path))
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
