"""
Phase R6: Comprehensive Evaluation & Statistical Validation Suite.
Evaluates Treatments A through H across Train, Validation, and Held-Out partitions:
- A: Original V1 Baseline
- B: R2 Treatment E (SFS + TIP)
- C: R4 Treatment D (Dense Semantic + Multi-Hop)
- D: R5 Treatment F (Full Typed Change-Impact)
- E: R5 Without Heuristic Edges
- F: R5 With Verified Graph Relationships Only
- G: R5 With Confidence-Calibrated Relationship Evidence
- H: Best Combined Model (Calibrated Impact + Verified Symbols + TIP)

Performs 10,000 repository-clustered bootstrap iterations and permutation tests.
Generates:
- PER_QUERY_RESULTS.jsonl
- master_metrics.json
- statistical_summary.json
"""

import os
import sys
import gzip
import json
import time
import numpy as np
from typing import Dict, List, Any, Tuple
from collections import defaultdict

r6_src = os.path.dirname(os.path.abspath(__file__))
if r6_src not in sys.path:
    sys.path.insert(0, r6_src)

from ranker_r6 import R6Ranker, TREATMENTS


def compute_metrics(eval_records: List[Dict[str, Any]]) -> Dict[str, float]:
    total = len(eval_records)
    if total == 0:
        return {}

    mrr_sum = 0.0
    hit1_count = 0
    r5_sum = 0.0
    r10_sum = 0.0
    r20_sum = 0.0
    complete_coverage_count = 0
    gold_candidates_recalled = 0
    gold_targets_total = 0

    for r in eval_records:
        ranks = r["gold_ranks"]
        golds = r["gold_files"]
        gold_targets_total += len(golds)

        if ranks:
            first_rank = ranks[0]
            mrr_sum += 1.0 / first_rank
            if first_rank == 1:
                hit1_count += 1

        r5_hits = sum(1 for rk in ranks if rk <= 5)
        r10_hits = sum(1 for rk in ranks if rk <= 10)
        r20_hits = sum(1 for rk in ranks if rk <= 20)

        r5_sum += r5_hits / len(golds)
        r10_sum += r10_hits / len(golds)
        r20_sum += r20_hits / len(golds)

        # Complete coverage: all gold targets in top 20
        if all(rk <= 20 for rk in ranks):
            complete_coverage_count += 1

        # Candidate recall
        gold_candidates_recalled += r["gold_candidates_in_pool"]

    return {
        "mrr": round(mrr_sum / total, 4),
        "hit1": round(hit1_count / total, 4),
        "recall_5": round(r5_sum / total, 4),
        "recall_10": round(r10_sum / total, 4),
        "recall_20": round(r20_sum / total, 4),
        "complete_coverage": round(complete_coverage_count / total, 4),
        "candidate_recall": round(gold_candidates_recalled / gold_targets_total, 4) if gold_targets_total > 0 else 1.0,
        "query_count": total,
    }


def clustered_bootstrap_ci(
    records_base: List[Dict[str, Any]],
    records_treat: List[Dict[str, Any]],
    n_iterations: int = 10000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Computes 95% CI on paired MRR delta resampling entire repository clusters."""
    rng = np.random.RandomState(seed)
    
    # Group by repo
    repo_to_deltas = defaultdict(list)
    for b, t in zip(records_base, records_treat):
        assert b["query_id"] == t["query_id"]
        assert b["repo"] == t["repo"]
        b_mrr = 1.0 / b["gold_ranks"][0] if b["gold_ranks"] else 0.0
        t_mrr = 1.0 / t["gold_ranks"][0] if t["gold_ranks"] else 0.0
        repo_to_deltas[b["repo"]].append(t_mrr - b_mrr)

    repos = list(repo_to_deltas.keys())
    n_clusters = len(repos)
    all_deltas = [d for deltas in repo_to_deltas.values() for d in deltas]
    point_estimate = float(np.mean(all_deltas))

    boot_deltas = []
    for _ in range(n_iterations):
        sample_repos = rng.choice(repos, size=n_clusters, replace=True)
        sample_deltas = []
        for r in sample_repos:
            sample_deltas.extend(repo_to_deltas[r])
        boot_deltas.append(float(np.mean(sample_deltas)))

    boot_deltas.sort()
    ci_lower = float(np.percentile(boot_deltas, 2.5))
    ci_upper = float(np.percentile(boot_deltas, 97.5))

    # Permutation test p-value
    null_deltas = []
    for _ in range(n_iterations):
        perm_deltas = []
        for r in repos:
            sign = rng.choice([-1.0, 1.0])
            for d in repo_to_deltas[r]:
                perm_deltas.append(d * sign)
        null_deltas.append(float(np.mean(perm_deltas)))

    p_value = float(np.mean(np.abs(null_deltas) >= np.abs(point_estimate)))

    return {
        "point_estimate": round(point_estimate, 4),
        "ci_95_lower": round(ci_lower, 4),
        "ci_95_upper": round(ci_upper, 4),
        "p_value": round(p_value, 4),
        "clusters": n_clusters,
        "n_iterations": n_iterations,
    }


def evaluate_all():
    bm_path = os.path.join(r6_src, "..", "independent_benchmark.json.gz")
    with gzip.open(bm_path, "rt", encoding="utf-8") as f:
        dataset = json.load(f)

    partitions = {"train": [], "val": [], "held_out": []}
    for item in dataset:
        partitions[item["partition"]].append(item)

    print(f"Loaded benchmark dataset: {len(dataset)} items.")
    print(f"Train: {len(partitions['train'])}, Val: {len(partitions['val'])}, Held-Out: {len(partitions['held_out'])}")

    all_per_query_results = []
    master_metrics = {}
    treatment_records = defaultdict(lambda: defaultdict(list))

    # Evaluate each partition
    for part_name, query_list in partitions.items():
        master_metrics[part_name] = {}
        for treat in TREATMENTS:
            eval_records = []
            latencies = []

            for q in query_list:
                qid = q["query_id"]
                repo = q["repo"]
                query_text = q["query_text"]
                seeds = q.get("seed_files", [])
                golds = q["_evaluator_gold"]["gold_files"]
                candidates = q["candidates"]

                t0 = time.perf_counter()
                ranked_cands = R6Ranker.rank_candidates(candidates, query_text, seeds, treat)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                latencies.append(latency_ms)

                ranked_paths = [c["path"] for c in ranked_cands]
                gold_ranks = []
                for g in golds:
                    if g in ranked_paths:
                        gold_ranks.append(ranked_paths.index(g) + 1)
                    else:
                        gold_ranks.append(999999)
                gold_ranks.sort()

                # Pool check
                cand_pool_paths = set(c["path"] for c in candidates)
                golds_in_pool = sum(1 for g in golds if g in cand_pool_paths)

                rec = {
                    "query_id": qid,
                    "repo": repo,
                    "language": q["language"],
                    "task_type": q["task_type"],
                    "treatment": treat,
                    "partition": part_name,
                    "gold_files": golds,
                    "gold_ranks": gold_ranks,
                    "gold_candidates_in_pool": golds_in_pool,
                    "latency_ms": round(latency_ms, 3),
                    "top_files": ranked_paths[:5],
                }
                eval_records.append(rec)
                treatment_records[part_name][treat].append(rec)

                # Record per query for JSONL
                all_per_query_results.append(rec)

            metrics = compute_metrics(eval_records)
            metrics["avg_latency_ms"] = round(float(np.mean(latencies)), 3)
            master_metrics[part_name][treat] = metrics
            print(f"[{part_name.upper()}] Treatment {treat}: MRR={metrics['mrr']}, Hit@1={metrics['hit1']}, R@20={metrics['recall_20']}, Latency={metrics['avg_latency_ms']}ms")

    # Run statistical validations: G vs B and H vs B
    stat_summary = {}
    for part in ["train", "val", "held_out"]:
        b_recs = treatment_records[part]["B"]
        d_recs = treatment_records[part]["D"]
        g_recs = treatment_records[part]["G"]
        h_recs = treatment_records[part]["H"]

        stat_summary[part] = {
            "D_vs_B": clustered_bootstrap_ci(b_recs, d_recs),
            "G_vs_B": clustered_bootstrap_ci(b_recs, g_recs),
            "H_vs_B": clustered_bootstrap_ci(b_recs, h_recs),
            "G_vs_D": clustered_bootstrap_ci(d_recs, g_recs),
        }

    # Save artifacts
    out_dir = os.path.join(r6_src, "..")
    
    # 1. PER_QUERY_RESULTS.jsonl
    jsonl_path = os.path.join(out_dir, "PER_QUERY_RESULTS.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in all_per_query_results:
            f.write(json.dumps(r) + "\n")
    print(f"Saved {len(all_per_query_results)} per-query records to: {os.path.abspath(jsonl_path)}")

    # 2. master_metrics.json
    metrics_path = os.path.join(out_dir, "master_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(master_metrics, f, indent=2)
    print(f"Saved master metrics to: {os.path.abspath(metrics_path)}")

    # 3. statistical_summary.json
    stat_path = os.path.join(out_dir, "statistical_summary.json")
    with open(stat_path, "w", encoding="utf-8") as f:
        json.dump(stat_summary, f, indent=2)
    print(f"Saved statistical summary to: {os.path.abspath(stat_path)}")


if __name__ == "__main__":
    evaluate_all()

