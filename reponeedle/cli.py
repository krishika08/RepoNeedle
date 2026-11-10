"""
Command-line interface for RepoNeedle.
"""

import sys
import os
import json
import argparse
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from reponeedle.engine import (
    RepoNeedleEngine,
    DEFAULT_MAX_FILE_SIZE_BYTES,
    validate_max_file_size_bytes,
    is_path_within_root,
    relpath_escapes_root,
)
from reponeedle.models import TaskType, BudgetConfig

# Maximum number of skipped paths listed in human-readable (non-JSON) stderr notices.
# JSON output always contains the complete list.
_MAX_SKIPPED_PATHS_SHOWN = 20


def resolve_and_validate_anchors(repo_dir: str, anchors: Optional[List[str]]) -> List[str]:
    """
    Validates and resolves anchor file paths against the repository directory.
    Returns normalized repository-relative paths with forward slashes.
    Raises ValueError if an anchor does not exist or falls outside the repository.
    """
    if not anchors:
        return []

    abs_repo = os.path.normpath(os.path.abspath(repo_dir))
    normalized: List[str] = []

    for a in anchors:
        if not a or not a.strip():
            continue
        raw_anchor = a.strip()

        # The exact spelling is tried first. On POSIX, a Windows-style spelling ("src\\a.py") is then
        # retried with forward slashes, consistent with retrieve(anchor_files=...). A real file whose
        # name contains a backslash still takes precedence. Containment checks below apply either way.
        spellings = [raw_anchor]
        if os.sep == "/" and "\\" in raw_anchor:
            spellings.append(raw_anchor.replace("\\", "/"))

        resolved_target = None
        for spelling in spellings:
            # Interpretation 1: relative to repo_dir (e.g. "auth/session.py" with --repo "dir").
            candidate_1 = os.path.normpath(os.path.join(abs_repo, spelling))
            # Interpretation 2: relative to the current working directory, or absolute.
            candidate_2 = os.path.normpath(os.path.abspath(spelling))
            if os.path.isfile(candidate_1):
                resolved_target = candidate_1
            elif os.path.isfile(candidate_2):
                resolved_target = candidate_2
            if resolved_target is not None:
                break

        if resolved_target is None:
            raise ValueError(
                f"Anchor file '{raw_anchor}' does not exist or is not a regular file within repository '{repo_dir}'."
            )

        # Ensure the resolved file is inside the repository root
        try:
            rel_to_repo = os.path.relpath(resolved_target, abs_repo)
        except ValueError:
            raise ValueError(
                f"Anchor file '{raw_anchor}' is located on a different drive than repository '{repo_dir}'."
            )

        # Component-aware traversal check ('..cache/x' is a legitimate name; '../x' is not).
        if relpath_escapes_root(rel_to_repo) or os.path.isabs(rel_to_repo):
            raise ValueError(
                f"Anchor file '{raw_anchor}' resolves outside repository root '{repo_dir}'."
            )

        # Canonical containment (symlinks / junctions), consistent with indexing: an anchor whose
        # link target lies outside the repository is rejected, so it cannot name excluded content.
        if not is_path_within_root(os.path.realpath(resolved_target), os.path.realpath(abs_repo)):
            raise ValueError(
                f"Anchor file '{raw_anchor}' is a link that resolves outside repository root '{repo_dir}'."
            )

        clean_rel = rel_to_repo.replace("\\", "/")
        if clean_rel not in normalized:
            normalized.append(clean_rel)

    return normalized


def build_parser() -> argparse.ArgumentParser:
    """Builds and returns the argument parser for RepoNeedle CLI."""
    parser = argparse.ArgumentParser(
        prog="reponeedle",
        description="Token-Budget-Aware, Workflow-Adaptive Repository Context Retrieval for AI Coding Agents.",
    )
    parser.add_argument("query", type=str, help="Coding task, issue description, or error traceback.")
    parser.add_argument("--repo", "-r", type=str, default=".", help="Path to repository root (default: current directory).")
    parser.add_argument("--budget", "-b", type=int, default=4000, help="Maximum context token budget (default: 4000).")
    parser.add_argument(
        "--task",
        "-t",
        type=str,
        default="auto",
        choices=["auto", "code2test", "comment2context", "trace2code", "edit2ripple", "selective"],
        help="Explicit workflow task type (default: auto).",
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        default="auto",
        choices=["auto", "compact", "complete"],
        help="CUD-Pack context delivery mode: compact (high-density spans) or complete (whole files). Default: auto.",
    )
    parser.add_argument(
        "--serialize",
        "-s",
        action="store_true",
        help="Print the full packaged markdown prompt to stdout.",
    )
    parser.add_argument(
        "--output-file",
        "-o",
        type=str,
        default=None,
        help="Save the serialized markdown prompt context to a specified file.",
    )
    parser.add_argument("--no-skeletons", action="store_true", help="Disallow structural skeleton mode; require full files.")
    parser.add_argument(
        "--ranker",
        "--ranking-engine",
        dest="ranker",
        type=str,
        default="legacy",
        choices=["legacy", "bm25", "arm101", "cascade", "change_impact"],
        help="Retrieval ranker architecture (default: legacy).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit results as machine-readable JSON on stdout without terminal formatting or ANSI codes.",
    )
    parser.add_argument(
        "--anchors",
        type=str,
        nargs="+",
        default=None,
        metavar="PATH",
        help="One or more seed or anchor file paths for change-impact analysis or ripple queries.",
    )
    parser.add_argument(
        "--include-context",
        action="store_true",
        help="Include the full rendered prompt context in the JSON response under 'rendered_context'.",
    )
    parser.add_argument(
        "--enable-experimental-abstention",
        action="store_true",
        help=(
            "Opt in to the EXPERIMENTAL, uncalibrated out-of-scope abstention heuristic "
            "(disabled by default; 0/82 correct abstentions on the ARB v2 selective split). "
            "'--task selective' does not enable it."
        ),
    )
    parser.add_argument(
        "--max-file-size-bytes",
        type=int,
        default=DEFAULT_MAX_FILE_SIZE_BYTES,
        metavar="BYTES",
        help=(
            f"Skip files strictly larger than this many bytes during indexing "
            f"(default: {DEFAULT_MAX_FILE_SIZE_BYTES}). Skipped paths are reported in diagnostics."
        ),
    )
    return parser


def _indexing_notice_lines(diag) -> List[str]:
    """Human-readable lines describing indexing exclusions (paths only, never contents)."""
    lines: List[str] = []
    if diag.skipped_large_files:
        lines.append(
            f"{diag.skipped_large_files} file(s) larger than {diag.max_file_size_bytes} bytes were not indexed:"
        )
        for p in diag.skipped_paths[:_MAX_SKIPPED_PATHS_SHOWN]:
            lines.append(f"  - {p}")
        remaining = len(diag.skipped_paths) - _MAX_SKIPPED_PATHS_SHOWN
        if remaining > 0:
            lines.append(f"  ... and {remaining} more (use --json for the full list)")
    if diag.skipped_unreadable_files:
        lines.append(f"{diag.skipped_unreadable_files} file(s) could not be read and were not indexed.")
    if diag.skipped_symlink_outside_repository:
        lines.append(
            f"{diag.skipped_symlink_outside_repository} linked file(s) resolve outside the repository "
            f"and were not read (reason: symlink_outside_repository):"
        )
        for p in diag.symlink_outside_repository_paths[:_MAX_SKIPPED_PATHS_SHOWN]:
            lines.append(f"  - {p}")
    if diag.max_files_reached:
        lines.append(f"Indexing stopped at the max_files limit ({diag.max_files}); remaining files were not indexed.")
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = build_parser()
    args = parser.parse_args(argv)

    # Validate repository path
    repo_path = os.path.abspath(args.repo)
    if not os.path.isdir(repo_path):
        sys.stderr.write(f"Error: Repository directory '{args.repo}' does not exist or is not a directory.\n")
        return 1

    # Validate and normalize anchor files
    try:
        normalized_anchors = resolve_and_validate_anchors(args.repo, args.anchors)
    except ValueError as err:
        sys.stderr.write(f"Error: {err}\n")
        return 1

    # Validate file-size limit before any indexing work
    try:
        max_file_size_bytes = validate_max_file_size_bytes(args.max_file_size_bytes)
    except (TypeError, ValueError) as err:
        sys.stderr.write(f"Error: {err}\n")
        return 1

    config = BudgetConfig(
        max_tokens=args.budget,
        allow_skeletons=not args.no_skeletons,
        mode=args.mode,
        enable_experimental_abstention=args.enable_experimental_abstention,
    )

    console = None
    if not args.json:
        console = Console()
        console.print(
            Panel(
                f"[bold cyan]RepoNeedle Context Retrieval[/bold cyan]\n"
                f"Target Repository: [green]{args.repo}[/green]\n"
                f"Query: [yellow]\"{args.query}\"[/yellow]\n"
                f"Token Budget: [magenta]{args.budget}[/magenta]\n"
                f"Ranker: [cyan]{args.ranker}[/cyan]"
                + (f"\nAnchors: [blue]{', '.join(normalized_anchors)}[/blue]" if normalized_anchors else "")
                + (
                    "\nAbstention: [yellow]EXPERIMENTAL heuristic enabled (uncalibrated)[/yellow]"
                    if args.enable_experimental_abstention else ""
                ),
                expand=False,
            )
        )
        with console.status("[bold green]Indexing repository..."):
            engine = RepoNeedleEngine.from_directory(
                args.repo, budget_config=config, max_file_size_bytes=max_file_size_bytes
            )
        # Indexing exclusions are diagnostics: always routed to stderr, never stdout.
        notice = _indexing_notice_lines(engine.indexing_diagnostics)
        if notice:
            Console(stderr=True).print(
                Panel("\n".join(notice), title="Indexing notice", border_style="yellow", expand=False),
                markup=False,
            )
    else:
        # The engine logs a summary WARNING to stderr when files are skipped; the full,
        # machine-readable list is emitted in the JSON payload under "indexing".
        engine = RepoNeedleEngine.from_directory(
            args.repo, budget_config=config, max_file_size_bytes=max_file_size_bytes
        )

    task_type = TaskType(args.task) if args.task != "auto" else None
    result = engine.retrieve(
        query=args.query,
        budget_tokens=args.budget,
        task_type=task_type,
        ranker=args.ranker,
        anchor_files=normalized_anchors,
    )

    # Handle output-file writing if requested
    if args.output_file:
        try:
            with open(args.output_file, "w", encoding="utf-8") as f:
                f.write(result.rendered_context)
            if not args.json and console:
                console.print(f"[bold green]Serialized prompt saved to:[/bold green] {args.output_file}")
        except Exception as exc:
            sys.stderr.write(f"Error saving output file '{args.output_file}': {exc}\n")
            return 1

    # JSON output branch
    if args.json:
        selected_list = []
        for rank, sf in enumerate(result.selected_files, start=1):
            selected_list.append({
                "rank": rank,
                "path": sf.path,
                "tier": sf.tier.value if hasattr(sf.tier, "value") else str(sf.tier),
                "token_count": int(sf.token_count),
                "score": round(float(sf.score), 4),
                "explanation": sf.explanation or "",
            })

        payload = {
            "schema_version": "1.2.0",
            "status": "abstained" if result.abstained else "success",
            "query": result.query,
            "repository": args.repo,
            "ranker": result.ranker or args.ranker,
            "task_type": result.task_type.value if hasattr(result.task_type, "value") else str(result.task_type),
            "abstained": bool(result.abstained),
            "explanation": result.explanation or "",
            "budget_tokens": int(result.budget_tokens),
            "total_tokens": int(result.total_tokens),
            "execution_time_ms": round(float(result.execution_time_ms), 2),
            "confidence_score": round(float(result.confidence_score), 4),
            "selected_files": selected_list,
            "abstention": result.abstention.model_dump() if result.abstention is not None else None,
            "indexing": engine.indexing_diagnostics.model_dump(),
        }

        if args.include_context or args.serialize:
            payload["rendered_context"] = result.rendered_context

        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    # Rich terminal output branch (existing behavior)
    if result.abstained:
        is_heuristic = result.abstention is not None and result.abstention.status == "evaluated"
        heading = "System Abstained (experimental heuristic)" if is_heuristic else "System Abstained"
        console.print(
            Panel(
                f"[bold red]{heading}[/bold red]\n"
                f"{result.explanation}\n"
                f"Confidence Score: {result.confidence_score:.3f}\n"
                f"Execution Time: {result.execution_time_ms:.1f}ms",
                border_style="red",
            )
        )
        return 0

    table = Table(
        title=f"Retrieved Context ({result.total_tokens}/{result.budget_tokens} tokens) - {result.execution_time_ms:.1f}ms"
    )
    table.add_column("Rank", justify="center", style="cyan")
    table.add_column("File Path", style="green")
    table.add_column("Tier", justify="center", style="magenta")
    table.add_column("Tokens", justify="right", style="yellow")
    table.add_column("Score", justify="right", style="blue")
    table.add_column("Explanation", style="white")

    for rank, sf in enumerate(result.selected_files, start=1):
        table.add_row(
            str(rank),
            sf.path,
            sf.tier.value.upper(),
            str(sf.token_count),
            f"{sf.score:.3f}",
            sf.explanation,
        )

    console.print(table)

    if args.serialize:
        console.print("\n[bold cyan]=== Serialized Context Prompt ===[/bold cyan]\n")
        try:
            print(result.rendered_context)
        except UnicodeEncodeError:
            enc = sys.stdout.encoding or "utf-8"
            print(result.rendered_context.encode(enc, errors="replace").decode(enc))

    return 0


if __name__ == "__main__":
    sys.exit(main())
