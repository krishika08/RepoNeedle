"""
Command-line interface for RepoNeedle.
"""

import sys
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import TaskType, BudgetConfig


def main():
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
    parser.add_argument("--no-skeletons", action="store_true", help="Disallow structural skeleton mode; require full files.")

    args = parser.parse_args()
    console = Console()

    console.print(Panel(f"[bold cyan]RepoNeedle Context Retrieval[/bold cyan]\nTarget Repository: [green]{args.repo}[/green]\nQuery: [yellow]\"{args.query}\"[/yellow]\nToken Budget: [magenta]{args.budget}[/magenta]", expand=False))

    config = BudgetConfig(
        max_tokens=args.budget,
        allow_skeletons=not args.no_skeletons,
    )

    with console.status("[bold green]Indexing repository..."):
        engine = RepoNeedleEngine.from_directory(args.repo, budget_config=config)

    task_type = TaskType(args.task) if args.task != "auto" else None
    result = engine.retrieve(query=args.query, budget_tokens=args.budget, task_type=task_type)

    if result.abstained:
        console.print(Panel(f"[bold red]System Abstained[/bold red]\n{result.explanation}\nConfidence Score: {result.confidence_score:.3f}\nExecution Time: {result.execution_time_ms:.1f}ms", border_style="red"))
        return

    table = Table(title=f"Retrieved Context ({result.total_tokens}/{result.budget_tokens} tokens) - {result.execution_time_ms:.1f}ms")
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


if __name__ == "__main__":
    main()
