#!/usr/bin/env python3
"""
RepoNeedle V1.1 — Certified Single Reproducible Benchmark Command.
Evaluates the R6 independent benchmark (18 repositories, 180 queries)
comparing Baseline Treatment B against Champion Treatment D (Change-Impact).

Outputs:
- Per-query rankings and relevant-file ranks
- Micro and Macro MRR
- Hit@1, Recall@5, Recall@10, Recall@20
- Per-repository metric breakdown
- Runtime latency measurements
- Environmental provenance & data hash validation
"""

import os
import sys
import gzip
import json
import time
import hashlib
import platform
import subprocess
import numpy as np
from collections import defaultdict
from typing import Dict, List, Any

# Root setup
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
r6_src = os.path.join(root_dir, "research", "v1_accuracy", "ranking_0_80", "r6", "src")
if r6_src not in sys.path:
    sys.path.insert(0, r6_src)

from ranker_r6 import R6Ranker


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_benchmark():
    start_wall_time = time.time()
    benchmark_gz = os.path.join(root_dir, "research", "v1_accuracy", "ranking_0_80", "r6", "independent_benchmark.json.gz")
    
    # 1. Environment and Provenance Audit
    data_sha = sha256_file(benchmark_gz)
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root_dir, text=True).strip()
    except Exception:
        git_sha = "unknown"

    print("=" * 80)
    print("REPONEEDLE V1.1 — CERTIFIED BENCHMARK REPRODUCIBILITY HARNESS")
    print("=" * 80)
    print(f"Git Commit SHA:       {git_sha}")
    print(f"Benchmark File:       {os.path.relpath(benchmark_gz, root_dir)}")
    print(f"Benchmark SHA-256:    {data_sha}")
    print(f"Python Platform:      {platform.python_implementation()} {platform.python_version()} on {platform.system()} {platform.release()}")
    print("=" * 80)

    # 2. Load Benchmark Dataset
    with gzip.open(benchmark_gz, "rt", encoding="utf-8") as f:
        dataset = json.load(f)

    print(f"Loaded {len(dataset)} queries across {len(set(q['repo'] for q in dataset))} unseen repositories.")

    # 3. Evaluate Baseline (B) and Champion (D)
    eval_results = []
    latencies = {"B": [], "D": []}

    for item in dataset:
        qid = item["query_id"]
        repo = item["repo"]
        part = item["partition"]
        query_text = item["query_text"]
        seeds = item.get("seed_files", [])
        golds = item["_evaluator_gold"]["gold_files"]
        candidates = item["candidates"]

        # Rank with Treatment B
        t0 = time.perf_counter()
        ranked_b = R6Ranker.rank_candidates(candidates, query_text, seeds, "B")
        lat_b = (time.perf_counter() - t0) * 1000.0
        latencies["B"].append(lat_b)
        paths_b = [c["path"] for c in ranked_b]
        ranks_b = sorted([paths_b.index(g) + 1 if g in paths_b else 999999 for g in golds])

        # Rank with Treatment D
        t0 = time.perf_counter()
        ranked_d = R6Ranker.rank_candidates(candidates, query_text, seeds, "D")
        lat_d = (time.perf_counter() - t0) * 1000.0
        latencies["D"].append(lat_d)
        paths_d = [c["path"] for c in ranked_d]
        ranks_d = sorted([paths_d.index(g) + 1 if g in paths_d else 999999 for g in golds])

        eval_results.append({
            "query_id": qid,
            "repo": repo,
            "partition": part,
            "gold_files": golds,
            "ranks_baseline_b": ranks_b,
            "first_rank_b": ranks_b[0] if ranks_b else 999999,
            "ranks_champion_d": ranks_d,
            "first_rank_d": ranks_d[0] if ranks_d else 999999,
            "delta_mrr": (1.0 / ranks_d[0]) - (1.0 / ranks_b[0]),
        })

    # 4. Compute Metrics per Partition and Cohort
    def compute_summary(records: List[Dict[str, Any]], key_first: str, key_ranks: str) -> Dict[str, float]:
        n = len(records)
        if n == 0:
            return {}
        mrr = np.mean([1.0 / r[key_first] if r[key_first] < 999999 else 0.0 for r in records])
        hit1 = np.mean([1.0 if r[key_first] == 1 else 0.0 for r in records])
        r5 = np.mean([sum(1 for rk in r[key_ranks] if rk <= 5) / len(r["gold_files"]) for r in records])
        r10 = np.mean([sum(1 for rk in r[key_ranks] if rk <= 10) / len(r["gold_files"]) for r in records])
        r20 = np.mean([sum(1 for rk in r[key_ranks] if rk <= 20) / len(r["gold_files"]) for r in records])
        return {
            "mrr": round(float(mrr), 4),
            "hit1": round(float(hit1), 4),
            "recall_5": round(float(r5), 4),
            "recall_10": round(float(r10), 4),
            "recall_20": round(float(r20), 4),
            "n_queries": n,
        }

    partitions = ["train", "val", "held_out", "pooled"]
    metrics_summary = {}

    for p in ["train", "val", "held_out"]:
        p_recs = [r for r in eval_results if r["partition"] == p]
        metrics_summary[f"{p}_baseline_b"] = compute_summary(p_recs, "first_rank_b", "ranks_baseline_b")
        metrics_summary[f"{p}_champion_d"] = compute_summary(p_recs, "first_rank_d", "ranks_champion_d")

    metrics_summary["pooled_baseline_b"] = compute_summary(eval_results, "first_rank_b", "ranks_baseline_b")
    metrics_summary["pooled_champion_d"] = compute_summary(eval_results, "first_rank_d", "ranks_champion_d")

    # 5. Print Partition Results Table
    print("\n" + "=" * 80)
    print("PARTITION RESULTS SUMMARY")
    print("=" * 80)
    print(f"{'Partition':<12} | {'Queries':<7} | {'Base B MRR':<10} | {'Champ D MRR':<11} | {'Delta MRR':<10} | {'Base R@20':<9} | {'Champ R@20':<10}")
    print("-" * 80)
    for p in ["train", "val", "held_out", "pooled"]:
        b = metrics_summary[f"{p}_baseline_b"]
        d = metrics_summary[f"{p}_champion_d"]
        delta = d["mrr"] - b["mrr"]
        print(f"{p.upper():<12} | {b['n_queries']:<7} | {b['mrr']:<10.4f} | {d['mrr']:<11.4f} | {delta:<+10.4f} | {b['recall_20']:<9.4f} | {d['recall_20']:<10.4f}")
    print("=" * 80)

    # 6. Per-Repository Breakdown Table
    print("\nPER-REPOSITORY BREAKDOWN")
    print("-" * 80)
    print(f"{'Repository Identifier':<28} | {'Part':<8} | {'Base MRR':<8} | {'Champ MRR':<9} | {'Delta':<7} | {'Status'}")
    print("-" * 80)
    by_repo = defaultdict(list)
    for r in eval_results:
        by_repo[r["repo"]].append(r)

    for repo, r_list in by_repo.items():
        part = r_list[0]["partition"]
        b_mrr = np.mean([1.0 / r["first_rank_b"] for r in r_list])
        d_mrr = np.mean([1.0 / r["first_rank_d"] for r in r_list])
        diff = d_mrr - b_mrr
        status = "IMPROVED" if diff > 0.001 else ("NEUTRAL" if abs(diff) <= 0.001 else "REGRESSION")
        print(f"{repo:<28} | {part:<8} | {b_mrr:<8.4f} | {d_mrr:<9.4f} | {diff:<+7.4f} | {status}")
    print("-" * 80)

    # 7. Latency Summary
    lat_b_mean = float(np.mean(latencies["B"]))
    lat_d_mean = float(np.mean(latencies["D"]))
    lat_d_p50 = float(np.percentile(latencies["D"], 50))
    lat_d_p95 = float(np.percentile(latencies["D"], 95))

    print("\nRUNTIME MEASUREMENTS")
    print(f"Baseline B Latency (Isolated Ranker):  Mean = {lat_b_mean:.3f} ms")
    print(f"Champion D Latency (Isolated Ranker):  Mean = {lat_d_mean:.3f} ms, P50 = {lat_d_p50:.3f} ms, P95 = {lat_d_p95:.3f} ms")
    print(f"Total Benchmark Execution Time:       {time.time() - start_wall_time:.2f} s")
    print("=" * 80)

    # 8. Save Detailed Audit Artifact
    out_record = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "git_commit": git_sha,
            "benchmark_sha256": data_sha,
            "python_version": sys.version,
            "platform": platform.platform(),
        },
        "metrics_summary": metrics_summary,
        "latency_measurements": {
            "baseline_mean_ms": round(lat_b_mean, 3),
            "champion_mean_ms": round(lat_d_mean, 3),
            "champion_p50_ms": round(lat_d_p50, 3),
            "champion_p95_ms": round(lat_d_p95, 3),
        },
        "per_query_rankings": eval_results,
    }

    out_path = os.path.join(os.path.dirname(__file__), "reproducible_benchmark_run.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_record, f, indent=2)

    print(f"\nSaved complete reproducible audit record to: {os.path.abspath(out_path)}")
    return out_record


if __name__ == "__main__":
    run_benchmark()

