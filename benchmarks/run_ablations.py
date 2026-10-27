"""
Component ablation study and repository-grouped train/test evaluation with bootstrap confidence intervals.
"""

import os
import sys
import json
import time
import numpy as np
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reponeedle.models import FileDoc, Query, TaskType, BudgetConfig, ContextTier
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.core.graph import RepoGraph
from reponeedle.core.tokenizer import estimate_tokens
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


def bootstrap_ci(data: List[float], n_resamples: int = 1000, ci: float = 0.95) -> Tuple[float, float, float]:
    """Computes mean and bootstrap confidence interval (low, high)."""
    if not data:
        return 0.0, 0.0, 0.0
    arr = np.array(data, dtype=np.float32)
    mean_val = float(np.mean(arr))
    if len(arr) <= 1 or np.all(arr == arr[0]):
        return mean_val, mean_val, mean_val

    rng = np.random.default_rng(seed=42)
    boot_means = []
    n = len(arr)
    for _ in range(n_resamples):
        sample = rng.choice(arr, size=n, replace=True)
        boot_means.append(np.mean(sample))

    alpha = (1.0 - ci) / 2.0
    low = float(np.percentile(boot_means, alpha * 100))
    high = float(np.percentile(boot_means, (1.0 - alpha) * 100))
    return mean_val, low, high


class AblationEngine:
    """Wraps RepoNeedle with toggleable ablation switches."""

    def __init__(
        self,
        docs: List[FileDoc],
        disable_router: bool = False,
        disable_abstainer: bool = False,
        disable_skeletons: bool = False,
    ):
        self.docs = docs
        self.disable_router = disable_router
        self.disable_abstainer = disable_abstainer
        self.disable_skeletons = disable_skeletons

        config = BudgetConfig(max_tokens=4000, allow_skeletons=not disable_skeletons)
        self.engine = RepoNeedleEngine.from_documents(docs, budget_config=config)

    def retrieve(self, sample: BenchmarkSample, budget_tokens: int = 4000):
        if self.disable_router:
            # Force fixed hybrid weights without task-specific routing
            query_obj = Query(text=sample.query, task_type=TaskType.COMMENT2CONTEXT, budget_tokens=budget_tokens)
        else:
            query_obj = Query(
                text=sample.query,
                task_type=sample.task_type,
                anchor_files=sample.anchor_files,
                budget_tokens=budget_tokens,
            )

        res = self.engine.retrieve(query_obj, budget_tokens=budget_tokens)
        
        if self.disable_abstainer and res.abstained:
            # Force ranker to pack candidates even if abstainer triggered
            q_terms = self.engine.tokenizer.tokenize_text(sample.query)
            lex_scores = self.engine.lexical_index.score(sample.query)
            sem_scores = self.engine.semantic_index.score(sample.query)
            fused = 0.5 * lex_scores + 0.5 * sem_scores
            candidates = []
            for idx, d in enumerate(self.docs):
                candidates.append((d, float(fused[idx]), {"lexical": float(lex_scores[idx]), "semantic": float(sem_scores[idx])}))
            packed = self.engine.budget_optimizer.pack_context(candidates, budget_tokens, q_terms)
            res.selected_files = packed
            res.abstained = False
            res.total_tokens = sum(f.token_count for f in packed)

        return res


def run_ablation_study() -> Dict[str, Any]:
    corpora = {
        "pallets/flask": build_flask_corpus(),
        "psf/requests": build_requests_corpus(),
        "tiangolo/fastapi": build_fastapi_held_out_corpus(),
    }
    samples = generate_benchmark_samples()

    configs = {
        "Full RepoNeedle": {"type": "rn", "router": True, "abstainer": True, "skeletons": True},
        "Ablation: No Router": {"type": "rn", "router": False, "abstainer": True, "skeletons": True},
        "Ablation: No Abstainer": {"type": "rn", "router": True, "abstainer": False, "skeletons": True},
        "Ablation: No Skeletons": {"type": "rn", "router": True, "abstainer": True, "skeletons": False},
        "Baseline: Static Hybrid": {"type": "hybrid"},
        "Baseline: BM25 Only": {"type": "bm25"},
        "Baseline: Dense Semantic Only": {"type": "dense"},
        "Baseline: RepoMap Only": {"type": "repomap"},
    }

    results = {
        name: {
            "all_mrr": [],
            "dev_mrr": [],
            "held_out_mrr": [],
            "recall@1": [],
            "recall@3": [],
            "irrelevant_tokens_4k": [],
            "selective_correct": [],
            "selective_total": 0,
            "task_mrr": defaultdict(list),
        }
        for name in configs
    }

    for sample in samples:
        repo_docs = corpora[sample.repo_name]
        gold_set = set(sample.gold_files)
        is_selective = (sample.task_type == TaskType.SELECTIVE)
        is_held_out = sample.is_held_out_repo

        for name, cfg in configs.items():
            if cfg["type"] == "rn":
                runner = AblationEngine(
                    repo_docs,
                    disable_router=not cfg["router"],
                    disable_abstainer=not cfg["abstainer"],
                    disable_skeletons=not cfg["skeletons"],
                )
                res = runner.retrieve(sample, budget_tokens=4000)
            elif cfg["type"] == "hybrid":
                res = StaticHybridBaseline(repo_docs).retrieve(sample.query, budget_tokens=4000)
            elif cfg["type"] == "bm25":
                res = BM25Baseline(repo_docs).retrieve(sample.query, budget_tokens=4000)
            elif cfg["type"] == "dense":
                res = DenseSemanticBaseline(repo_docs).retrieve(sample.query, budget_tokens=4000)
            elif cfg["type"] == "repomap":
                res = RepoMapBaseline(repo_docs).retrieve(sample.query, budget_tokens=4000)

            ranked_paths = [f.path for f in res.selected_files]

            if is_selective:
                results[name]["selective_total"] += 1
                is_correct = (res.abstained or len(res.selected_files) == 0)
                results[name]["selective_correct"].append(1.0 if is_correct else 0.0)
                waste = sum(f.token_count for f in res.selected_files)
                results[name]["irrelevant_tokens_4k"].append(waste)
                continue

            rr = RetrievalEvaluator.reciprocal_rank(ranked_paths, gold_set)
            r1 = RetrievalEvaluator.recall_at_k(ranked_paths, gold_set, 1)
            r3 = RetrievalEvaluator.recall_at_k(ranked_paths, gold_set, 3)

            results[name]["all_mrr"].append(rr)
            results[name]["recall@1"].append(r1)
            results[name]["recall@3"].append(r3)

            if is_held_out:
                results[name]["held_out_mrr"].append(rr)
            else:
                results[name]["dev_mrr"].append(rr)

            pack_metrics = RetrievalEvaluator.evaluate_budgeted_packing(res.selected_files, gold_set, 4000)
            results[name]["irrelevant_tokens_4k"].append(pack_metrics["irrelevant_tokens"])

            results[name]["task_mrr"][sample.task_type.value].append(rr)

    summary = {}
    for name, d in results.items():
        mrr_mean, mrr_low, mrr_high = bootstrap_ci(d["all_mrr"])
        dev_mean, dev_low, dev_high = bootstrap_ci(d["dev_mrr"])
        held_mean, held_low, held_high = bootstrap_ci(d["held_out_mrr"])

        summary[name] = {
            "Overall_MRR": mrr_mean,
            "MRR_95_CI": [mrr_low, mrr_high],
            "Dev_MRR (N=8)": dev_mean,
            "HeldOut_MRR (N=4)": held_mean,
            "Recall@1": float(np.mean(d["recall@1"])) if d["recall@1"] else 0.0,
            "Recall@3": float(np.mean(d["recall@3"])) if d["recall@3"] else 0.0,
            "IrrelevantTokens@4k": float(np.mean(d["irrelevant_tokens_4k"])) if d["irrelevant_tokens_4k"] else 0.0,
            "SelectiveAccuracy": float(np.mean(d["selective_correct"])) if d["selective_correct"] else 0.0,
            "Task_MRR": {t: float(np.mean(vals)) for t, vals in d["task_mrr"].items()},
        }

    return summary


def main():
    print("=========================================================================")
    print("Executing RepoNeedle Component Ablation Study & Bootstrap CI Analysis")
    print("=========================================================================")
    summary = run_ablation_study()

    print(f"\n{'System / Ablation':<30} | {'MRR':<8} | {'95% CI':<15} | {'Dev MRR':<9} | {'Held-out':<9} | {'Rec@1':<7} | {'Rec@3':<7} | {'Waste Tok':<9} | {'Sel Acc'}")
    print("-" * 120)

    for name, m in summary.items():
        ci_str = f"[{m['MRR_95_CI'][0]:.3f}, {m['MRR_95_CI'][1]:.3f}]"
        print(
            f"{name:<30} | "
            f"{m['Overall_MRR']:<8.3f} | "
            f"{ci_str:<15} | "
            f"{m['Dev_MRR (N=8)']:<9.3f} | "
            f"{m['HeldOut_MRR (N=4)']:<9.3f} | "
            f"{m['Recall@1']:<7.3f} | "
            f"{m['Recall@3']:<7.3f} | "
            f"{m['IrrelevantTokens@4k']:<9.0f} | "
            f"{m['SelectiveAccuracy']*100:.1f}%"
        )

    out_file = Path("benchmarks/results/ablation_study_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nAblation study results written to: {out_file}")


if __name__ == "__main__":
    main()
