"""
Comprehensive benchmark runner comparing RepoNeedle against baselines.
Evaluates IR metrics, token budget context coverage, and selective abstention.
"""

import time
from typing import List, Dict, Any, Set
import numpy as np
from rich.console import Console
from rich.table import Table

from reponeedle.models import FileDoc, Query, TaskType, BudgetConfig
from reponeedle.engine import RepoNeedleEngine
from benchmarks.evaluator import RetrievalEvaluator
from benchmarks.baselines import (
    BM25Baseline,
    RepoMapBaseline,
    DenseSemanticBaseline,
    StaticHybridBaseline,
)
from benchmarks.data.generator import (
    build_flask_corpus,
    build_requests_corpus,
    build_fastapi_held_out_corpus,
    generate_benchmark_samples,
    BenchmarkSample,
)


class BenchmarkRunner:
    """
    Orchestrates benchmark runs across all systems, datasets, and token budgets.
    """

    def __init__(self):
        self.corpora: Dict[str, List[FileDoc]] = {
            "pallets/flask": build_flask_corpus(),
            "psf/requests": build_requests_corpus(),
            "tiangolo/fastapi": build_fastapi_held_out_corpus(),
        }
        self.samples = generate_benchmark_samples()

    def run_all(self, budgets: List[int] = [2000, 4000, 8000]) -> Dict[str, Any]:
        """
        Executes full benchmark suite across all baselines and RepoNeedle.
        """
        systems = [
            "BM25",
            "RepoMap",
            "DenseSemantic",
            "StaticHybrid",
            "RepoNeedle",
        ]

        # Results container
        # system -> metric -> values
        results: Dict[str, Dict[str, Any]] = {
            sys_name: {
                "mrr": [],
                "recall@1": [],
                "recall@3": [],
                "ndcg@3": [],
                "bcc_2k": [],
                "bcc_4k": [],
                "bcc_8k": [],
                "irrelevant_tokens_4k": [],
                "selective_correct": [],
                "selective_total": 0,
                "latencies_ms": [],
                "by_task": {},
                "held_out_mrr": [],
                "held_out_bcc_4k": [],
            }
            for sys_name in systems
        }

        for sample in self.samples:
            repo_docs = self.corpora[sample.repo_name]
            gold_set = set(sample.gold_files)
            is_selective = (sample.task_type == TaskType.SELECTIVE)

            # Initialize system instances for this repository
            instances = {
                "BM25": BM25Baseline(repo_docs),
                "RepoMap": RepoMapBaseline(repo_docs),
                "DenseSemantic": DenseSemanticBaseline(repo_docs),
                "StaticHybrid": StaticHybridBaseline(repo_docs),
                "RepoNeedle": RepoNeedleEngine.from_documents(repo_docs),
            }

            for sys_name, runner in instances.items():
                t0 = time.perf_counter()

                # 1. Ranking evaluation (using standard 4k budget)
                if sys_name == "RepoNeedle":
                    res_4k = runner.retrieve(
                        query=Query(
                            text=sample.query,
                            task_type=sample.task_type,
                            anchor_files=sample.anchor_files,
                            budget_tokens=4000,
                        )
                    )
                else:
                    res_4k = runner.retrieve(sample.query, budget_tokens=4000)

                latency_ms = (time.perf_counter() - t0) * 1000
                results[sys_name]["latencies_ms"].append(latency_ms)

                ranked_paths = [f.path for f in res_4k.selected_files]

                # Selective task evaluation
                if is_selective:
                    results[sys_name]["selective_total"] += 1
                    # A correct selective decision on a no-gold task is returning 0 files (or abstaining)
                    is_correct = (res_4k.abstained or len(res_4k.selected_files) == 0)
                    results[sys_name]["selective_correct"].append(1.0 if is_correct else 0.0)
                    # For selective tasks, irrelevant tokens are any tokens returned
                    waste = sum(f.token_count for f in res_4k.selected_files)
                    results[sys_name]["irrelevant_tokens_4k"].append(waste)
                    continue

                # Positive retrieval tasks evaluation:
                rr = RetrievalEvaluator.reciprocal_rank(ranked_paths, gold_set)
                r1 = RetrievalEvaluator.recall_at_k(ranked_paths, gold_set, 1)
                r3 = RetrievalEvaluator.recall_at_k(ranked_paths, gold_set, 3)
                ndcg3 = RetrievalEvaluator.ndcg_at_k(ranked_paths, gold_set, 3)

                results[sys_name]["mrr"].append(rr)
                results[sys_name]["recall@1"].append(r1)
                results[sys_name]["recall@3"].append(r3)
                results[sys_name]["ndcg@3"].append(ndcg3)

                if sample.is_held_out_repo:
                    results[sys_name]["held_out_mrr"].append(rr)

                # Budgeted Context Coverage across 2k, 4k, 8k
                for b in [2000, 4000, 8000]:
                    if sys_name == "RepoNeedle":
                        res_b = runner.retrieve(
                            query=Query(
                                text=sample.query,
                                task_type=sample.task_type,
                                anchor_files=sample.anchor_files,
                                budget_tokens=b,
                            )
                        )
                    else:
                        res_b = runner.retrieve(sample.query, budget_tokens=b)

                    pack_metrics = RetrievalEvaluator.evaluate_budgeted_packing(
                        res_b.selected_files, gold_set, b
                    )
                    b_key = f"bcc_{b // 1000}k"
                    results[sys_name][b_key].append(pack_metrics["coverage"])

                    if b == 4000:
                        results[sys_name]["irrelevant_tokens_4k"].append(
                            pack_metrics["irrelevant_tokens"]
                        )
                        if sample.is_held_out_repo:
                            results[sys_name]["held_out_bcc_4k"].append(
                                pack_metrics["coverage"]
                            )

                # Track per task type breakdown
                task_key = sample.task_type.value
                if task_key not in results[sys_name]["by_task"]:
                    results[sys_name]["by_task"][task_key] = {"mrr": [], "bcc_4k": []}
                results[sys_name]["by_task"][task_key]["mrr"].append(rr)
                results[sys_name]["by_task"][task_key]["bcc_4k"].append(
                    results[sys_name]["bcc_4k"][-1]
                )

        # Aggregate metrics
        summary = {}
        for sys_name, d in results.items():
            summary[sys_name] = {
                "MRR": float(np.mean(d["mrr"])) if d["mrr"] else 0.0,
                "Recall@1": float(np.mean(d["recall@1"])) if d["recall@1"] else 0.0,
                "Recall@3": float(np.mean(d["recall@3"])) if d["recall@3"] else 0.0,
                "nDCG@3": float(np.mean(d["ndcg@3"])) if d["ndcg@3"] else 0.0,
                "BCC@2k": float(np.mean(d["bcc_2k"])) if d["bcc_2k"] else 0.0,
                "BCC@4k": float(np.mean(d["bcc_4k"])) if d["bcc_4k"] else 0.0,
                "BCC@8k": float(np.mean(d["bcc_8k"])) if d["bcc_8k"] else 0.0,
                "IrrelevantTokens@4k": float(np.mean(d["irrelevant_tokens_4k"])) if d["irrelevant_tokens_4k"] else 0.0,
                "SelectiveAccuracy": float(np.mean(d["selective_correct"])) if d["selective_correct"] else 0.0,
                "AvgLatencyMs": float(np.mean(d["latencies_ms"])),
                "HeldOutMRR": float(np.mean(d["held_out_mrr"])) if d["held_out_mrr"] else 0.0,
                "HeldOutBCC@4k": float(np.mean(d["held_out_bcc_4k"])) if d["held_out_bcc_4k"] else 0.0,
                "TaskBreakdown": {
                    t: {
                        "MRR": float(np.mean(vals["mrr"])),
                        "BCC@4k": float(np.mean(vals["bcc_4k"])),
                    }
                    for t, vals in d["by_task"].items()
                },
            }

        return summary

    def print_summary_table(self, summary: Dict[str, Any]):
        """Prints formatted benchmark comparison table using rich."""
        console = Console()
        table = Table(title="[bold green]RepoNeedle Benchmark Results: System Comparison[/bold green]")
        table.add_column("System", style="bold cyan")
        table.add_column("MRR", justify="right", style="green")
        table.add_column("Recall@1", justify="right")
        table.add_column("Recall@3", justify="right")
        table.add_column("BCC@2k", justify="right", style="yellow")
        table.add_column("BCC@4k", justify="right", style="bold yellow")
        table.add_column("BCC@8k", justify="right")
        table.add_column("Irrel Tokens", justify="right", style="magenta")
        table.add_column("Selective Acc", justify="right", style="blue")
        table.add_column("Held-out BCC", justify="right", style="bold green")
        table.add_column("Latency (ms)", justify="right")

        for sys_name, m in summary.items():
            table.add_row(
                sys_name,
                f"{m['MRR']:.3f}",
                f"{m['Recall@1']:.3f}",
                f"{m['Recall@3']:.3f}",
                f"{m['BCC@2k']:.3f}",
                f"{m['BCC@4k']:.3f}",
                f"{m['BCC@8k']:.3f}",
                f"{m['IrrelevantTokens@4k']:.0f}",
                f"{m['SelectiveAccuracy'] * 100:.1f}%",
                f"{m['HeldOutBCC@4k']:.3f}",
                f"{m['AvgLatencyMs']:.2f}ms",
            )

        console.print(table)

