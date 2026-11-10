"""
Server entrypoint and factory for RepoNeedle Native MCP Server.
"""

import os
import sys
import time
import argparse
from typing import Optional, List

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None

from reponeedle.engine import (
    RepoNeedleEngine,
    DEFAULT_MAX_FILE_SIZE_BYTES,
    validate_max_file_size_bytes,
)
from reponeedle.models import BudgetConfig
from reponeedle.mcp.tools import register_tools


def create_mcp_server(
    repo_dir: str = ".",
    budget: int = 4000,
    allow_skeletons: bool = True,
    mode: str = "auto",
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
) -> "FastMCP":
    """
    Factory function creating and configuring a RepoNeedle FastMCP server instance.
    Indexes the repository once at startup and reuses the in-memory engine across tool calls.
    """
    if FastMCP is None:
        raise ImportError(
            "The RepoNeedle MCP server requires the 'mcp' extra. "
            "Install it via: pip install 'reponeedle[mcp]'"
        )

    max_file_size_bytes = validate_max_file_size_bytes(max_file_size_bytes)
    abs_repo = os.path.realpath(os.path.abspath(repo_dir))
    if not os.path.isdir(abs_repo):
        raise ValueError(f"Repository directory '{repo_dir}' does not exist or is not a directory.")

    sys.stderr.write(f"[reponeedle-mcp] Indexing repository: {abs_repo} ...\n")
    sys.stderr.flush()

    start_time = time.perf_counter()
    config = BudgetConfig(
        max_tokens=budget,
        allow_skeletons=allow_skeletons,
        mode=mode,
    )
    engine = RepoNeedleEngine.from_directory(
        abs_repo, budget_config=config, max_file_size_bytes=max_file_size_bytes
    )
    init_time_ms = (time.perf_counter() - start_time) * 1000

    sys.stderr.write(
        f"[reponeedle-mcp] Repository indexed successfully ({len(engine.docs)} files in {init_time_ms:.1f}ms).\n"
    )
    diag = engine.indexing_diagnostics
    if (diag.skipped_large_files or diag.skipped_unreadable_files or diag.max_files_reached
            or diag.skipped_symlink_outside_repository):
        sys.stderr.write(
            f"[reponeedle-mcp] Indexing exclusions: {diag.skipped_large_files} file(s) over "
            f"{diag.max_file_size_bytes} bytes, {diag.skipped_unreadable_files} unreadable"
            + (f", {diag.skipped_symlink_outside_repository} linked outside the repository (not read)"
               if diag.skipped_symlink_outside_repository else "")
            + (f", stopped at max_files={diag.max_files}" if diag.max_files_reached else "")
            + ". Call reponeedle_inspect for the skipped paths.\n"
        )
    sys.stderr.flush()

    app = FastMCP(
        name="reponeedle",
        instructions=(
            "RepoNeedle is a CPU-native, token-budget-aware repository context retrieval engine. "
            "Use reponeedle_retrieve to find code for tasks, reponeedle_change_impact to assess refactoring risks, "
            "and reponeedle_inspect to view repository index metadata."
        ),
    )

    register_tools(app=app, engine=engine, repo_dir=abs_repo, init_time_ms=init_time_ms)
    _set_server_version(app)
    return app


def _set_server_version(app) -> None:
    """
    Report RepoNeedle's package version as MCP `serverInfo.version`.

    FastMCP does not accept a version argument; its low-level server falls back to the MCP SDK's
    own version when none is set. Only `serverInfo.version` changes; the negotiated protocol version
    and the SDK dependency are unaffected.
    """
    from reponeedle import __version__
    low_level = getattr(app, "_mcp_server", None)
    if low_level is not None and hasattr(low_level, "version"):
        low_level.version = __version__


def build_parser() -> argparse.ArgumentParser:
    """Builds and returns CLI argument parser for the MCP server."""
    parser = argparse.ArgumentParser(
        prog="reponeedle-mcp",
        description="Local Model Context Protocol (MCP) server for RepoNeedle repository retrieval.",
    )
    parser.add_argument(
        "--repo",
        "-r",
        type=str,
        default=".",
        help="Path to repository root (default: current directory).",
    )
    parser.add_argument(
        "--budget",
        "-b",
        type=int,
        default=4000,
        help="Default context token budget (default: 4000).",
    )
    parser.add_argument(
        "--transport",
        type=str,
        default="stdio",
        choices=["stdio"],
        help="MCP transport protocol (default: stdio).",
    )
    parser.add_argument(
        "--no-skeletons",
        action="store_true",
        help="Disallow structural skeleton mode; require full files.",
    )
    parser.add_argument(
        "--max-file-size-bytes",
        type=int,
        default=DEFAULT_MAX_FILE_SIZE_BYTES,
        metavar="BYTES",
        help=(
            f"Skip files strictly larger than this many bytes during indexing "
            f"(default: {DEFAULT_MAX_FILE_SIZE_BYTES}). Skipped paths are reported by reponeedle_inspect."
        ),
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entrypoint for reponeedle-mcp executable.
    Communicates via STDIO. All diagnostic logs are sent to STDERR.
    """
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if FastMCP is None:
        sys.stderr.write(
            "Error: The 'mcp' extra is not installed.\n"
            "Please install it using:\n"
            "    pip install 'reponeedle[mcp]'\n"
        )
        sys.stderr.flush()
        return 1

    parser = build_parser()
    args = parser.parse_args(argv)

    abs_repo = os.path.realpath(os.path.abspath(args.repo))
    if not os.path.isdir(abs_repo):
        sys.stderr.write(f"Error: Repository directory '{args.repo}' does not exist or is not a directory.\n")
        sys.stderr.flush()
        return 1

    try:
        validate_max_file_size_bytes(args.max_file_size_bytes)
    except (TypeError, ValueError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        sys.stderr.flush()
        return 1

    try:
        app = create_mcp_server(
            repo_dir=abs_repo,
            budget=args.budget,
            allow_skeletons=not args.no_skeletons,
            max_file_size_bytes=args.max_file_size_bytes,
        )
    except Exception as exc:
        sys.stderr.write(f"Fatal error initializing RepoNeedle MCP server: {exc}\n")
        sys.stderr.flush()
        return 1

    sys.stderr.write("[reponeedle-mcp] Server ready. Listening for JSON-RPC messages on STDIO...\n")
    sys.stderr.flush()

    try:
        app.run(transport="stdio")
        return 0
    except (KeyboardInterrupt, SystemExit):
        sys.stderr.write("[reponeedle-mcp] Server shut down gracefully.\n")
        sys.stderr.flush()
        return 0
    except Exception as exc:
        sys.stderr.write(f"[reponeedle-mcp] Unhandled server error: {exc}\n")
        sys.stderr.flush()
        return 1


if __name__ == "__main__":
    sys.exit(main())
