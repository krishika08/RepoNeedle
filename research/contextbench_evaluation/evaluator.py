"""
Official ContextBench Metric Evaluator and Statistical Analysis Harness.

Calculates:
- File-level MRR (Mean Reciprocal Rank of first gold target)
- Multi-target fractional Recall@K (K=1, 5, 10, 20)
- Binary Hit@K
- Repository-clustered bootstrap confidence intervals (10,000 resamples clustered by repo)
- Paired statistical tests (Wilcoxon signed-rank)

Strictly preserves total denominator across all evaluated tasks.
"""

import json
from collections import defaultdict
from typing import Dict, Any, List, Tuple
import numpy as np
from scipy.stats import wilcoxon


def extract_gold_files(gold_context: Any) -> List[str]:
    """Extracts unique normalized file paths from ContextBench gold_context."""
    if isinstance(gold_context, str):
        try:
            gold_context = json.loads(gold_context)
        except Exception:
            pass

    files = set()
    if isinstance(gold_context, list):
        for item in gold_context:
            if isinstance(item, str):
                files.add(item.replace("\\", "/"))
            elif isinstance(item, dict) and "path" in item:
                files.add(item["path"].replace("\\", "/"))
            elif isinstance(item, dict) and "file" in item:
                files.add(item["file"].replace("\\", "/"))
    elif isinstance(gold_context, dict):
        for k in gold_context.keys():
            files.add(str(k).replace("\\", "/"))

    return sorted(list(files))


def evaluate_task_prediction(gold_files: List[str], ranked_files: List[str]) -> Dict[str, float]:
    """
    Computes file-level metrics for a single prediction against gold files.
    """
    norm_gold = set(f.replace("\\", "/").lower() for f in gold_files)
    norm_ranked = [f.replace("\\", "/").lower() for f in ranked_files]

    if not norm_gold:
        return {
            "mrr": 0.0,
            "recall_at_1": 0.0,
            "recall_at_5": 0.0,
            "recall_at_10": 0.0,
            "recall_at_20": 0.0,
            "hit_at_20": 0.0,
        }

    # 1. MRR: Reciprocal rank of first gold needle
    rr = 0.0
    for rank_idx, f in enumerate(norm_ranked, start=1):
        if f in norm_gold:
            rr = 1.0 / float(rank_idx)
            break

    # 2. Multi-target fractional Recall@K
    n_gold = float(len(norm_gold))
    r1 = len(norm_gold.intersection(norm_ranked[:1])) / n_gold
    r5 = len(norm_gold.intersection(norm_ranked[:5])) / n_gold
    r10 = len(norm_gold.intersection(norm_ranked[:10])) / n_gold
    r20 = len(norm_gold.intersection(norm_ranked[:20])) / n_gold

    # 3. Binary Hit@20
    hit20 = 1.0 if len(norm_gold.intersection(norm_ranked[:20])) > 0 else 0.0

    return {
        "mrr": rr,
        "recall_at_1": r1,
        "recall_at_5": r5,
        "recall_at_10": r10,
        "recall_at_20": r20,
        "hit_at_20": hit20,
    }


def compute_repository_clustered_ci(
    per_task_results: List[Dict[str, Any]],
    metric_key: str = "mrr",
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """
    Computes mean metric and 95% bootstrap confidence interval clustered by repository.
    Resamples entire repository clusters rather than individual queries to account
    for within-repository correlation.
    """
    repo_clusters = defaultdict(list)
    for res in per_task_results:
        repo = res.get("repo", "unknown")
        repo_clusters[repo].append(float(res[metric_key]))

    unique_repos = list(repo_clusters.keys())
    if not unique_repos:
        return 0.0, 0.0, 0.0

    total_tasks = sum(len(v) for v in repo_clusters.values())
    raw_mean = sum(sum(v) for v in repo_clusters.values()) / float(total_tasks)

    rng = np.random.RandomState(seed)
    boot_means = []
    n_repos = len(unique_repos)

    for _ in range(n_bootstrap):
        sampled_repos = rng.choice(unique_repos, size=n_repos, replace=True)
        sampled_scores = []
        for r in sampled_repos:
            sampled_scores.extend(repo_clusters[r])
        boot_means.append(np.mean(sampled_scores))

    ci_low, ci_high = np.percentile(boot_means, [2.5, 97.5])
    return float(raw_mean), float(ci_low), float(ci_high)
