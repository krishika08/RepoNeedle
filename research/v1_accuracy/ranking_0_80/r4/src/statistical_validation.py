"""
Repository-Clustered Statistical Validation for Phase R4.
Evaluates 10,000-round clustered bootstrap confidence intervals, empirical P*(Delta <= 0),
and permutation tests for Treatments D, H, and A.
"""
import os
import sys
import json
import random
import numpy as np
from typing import Dict, List, Tuple
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "r2", "src"))

from split import load_data, TRAIN_REPOS, VAL_REPOS, HELD_OUT_REPOS

BOOTSTRAP_ROUNDS = 10000
RANDOM_SEED = 42


def run_statistical_validation():
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    jsonl_path = os.path.join(os.path.dirname(__file__), "..", "PER_QUERY_COMPARISON.jsonl")
    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    assert len(records) == 345, f"Expected 345 records, got {len(records)}"

    split_records = defaultdict(list)
    for r in records:
        split_records[r["split"]].append(r)

    print("=== Phase R4 Repository-Clustered Statistical Validation ===")

    stats_summary = {}

    for comp_treatment in ["D", "H"]:
        stats_summary[comp_treatment] = {}
        print(f"\n==================== EVALUATING TREATMENT {comp_treatment} VS BASELINE A ====================")

        for s_name in ["val", "train", "held_out", "overall"]:
            if s_name == "overall":
                sub = records
            else:
                sub = split_records[s_name]

            repos = sorted(list(set(r["repo"] for r in sub)))
            repo_to_records = defaultdict(list)
            for r in sub:
                repo_to_records[r["repo"]].append(r)

            mrr_a = np.mean([r["treatments"]["A"]["reciprocal_rank"] for r in sub])
            mrr_comp = np.mean([r["treatments"][comp_treatment]["reciprocal_rank"] for r in sub])
            observed_delta = mrr_comp - mrr_a

            # 1. Repository-Clustered Bootstrap
            boot_deltas_clustered = []
            for _ in range(BOOTSTRAP_ROUNDS):
                resampled_repos = random.choices(repos, k=len(repos))
                resampled_records = []
                for rp in resampled_repos:
                    resampled_records.extend(repo_to_records[rp])

                b_mrr_a = np.mean([r["treatments"]["A"]["reciprocal_rank"] for r in resampled_records])
                b_mrr_comp = np.mean([r["treatments"][comp_treatment]["reciprocal_rank"] for r in resampled_records])
                boot_deltas_clustered.append(b_mrr_comp - b_mrr_a)

            ci_clustered_lower = float(np.percentile(boot_deltas_clustered, 2.5))
            ci_clustered_upper = float(np.percentile(boot_deltas_clustered, 97.5))
            p_nonpos_clustered = float(np.mean(np.array(boot_deltas_clustered) <= 0.0))

            # 2. Query-Level Bootstrap
            boot_deltas_query = []
            for _ in range(BOOTSTRAP_ROUNDS):
                resampled = random.choices(sub, k=len(sub))
                b_mrr_a = np.mean([r["treatments"]["A"]["reciprocal_rank"] for r in resampled])
                b_mrr_comp = np.mean([r["treatments"][comp_treatment]["reciprocal_rank"] for r in resampled])
                boot_deltas_query.append(b_mrr_comp - b_mrr_a)

            ci_query_lower = float(np.percentile(boot_deltas_query, 2.5))
            ci_query_upper = float(np.percentile(boot_deltas_query, 97.5))
            p_nonpos_query = float(np.mean(np.array(boot_deltas_query) <= 0.0))

            # 3. Permutation Test
            diffs = [r["treatments"][comp_treatment]["reciprocal_rank"] - r["treatments"]["A"]["reciprocal_rank"] for r in sub]
            perm_deltas = []
            for _ in range(BOOTSTRAP_ROUNDS):
                signs = np.random.choice([-1, 1], size=len(diffs))
                perm_deltas.append(np.mean(np.array(diffs) * signs))
            p_val_permutation = float(np.mean(np.abs(perm_deltas) >= np.abs(observed_delta)))

            stats_summary[comp_treatment][s_name] = {
                "num_queries": len(sub),
                "num_repos": len(repos),
                "mrr_a": float(mrr_a),
                "mrr_comp": float(mrr_comp),
                "observed_delta": float(observed_delta),
                "ci_clustered_95": [ci_clustered_lower, ci_clustered_upper],
                "ci_clustered_width": ci_clustered_upper - ci_clustered_lower,
                "p_nonpos_clustered": p_nonpos_clustered,
                "ci_query_95": [ci_query_lower, ci_query_upper],
                "ci_query_width": ci_query_upper - ci_query_lower,
                "p_nonpos_query": p_nonpos_query,
                "p_val_permutation": p_val_permutation,
            }

            print(f"\n--- Split: {s_name.upper()} ({len(sub)} queries, {len(repos)} repos) ---")
            print(f"  MRR(A):            {mrr_a:.4f}")
            print(f"  MRR({comp_treatment}):            {mrr_comp:.4f}")
            print(f"  Delta MRR:         {observed_delta:+.4f}")
            print(f"  Repo-Clustered CI: [{ci_clustered_lower:+.4f}, {ci_clustered_upper:+.4f}] (Width: {ci_clustered_upper - ci_clustered_lower:.4f})")
            print(f"  P*(Delta <= 0):    {p_nonpos_clustered:.4f}")
            print(f"  Query-Level CI:    [{ci_query_lower:+.4f}, {ci_query_upper:+.4f}] (Width: {ci_query_upper - ci_query_lower:.4f})")
            print(f"  Permutation p-val: {p_val_permutation:.4f}")

    # Candidate pool recall check
    train_data, val_data, held_out_data = load_data()
    all_data = train_data + val_data + held_out_data
    total_golds = sum(len(d["gold_files"]) for d in all_data)
    recovered_golds = sum(len(set(d["gold_files"]) & set(c["path"] for c in d["candidates"])) for d in all_data)

    stats_summary["candidate_recall"] = {
        "total_golds": total_golds,
        "recovered_golds": recovered_golds,
        "recall_pct": (recovered_golds / total_golds) * 100.0 if total_golds else 0.0,
    }
    print(f"\nCandidate Pool Gold Recall: {recovered_golds}/{total_golds} ({(recovered_golds / total_golds) * 100.0:.2f}%)")

    # Save to stats.json
    out_path = os.path.join(os.path.dirname(__file__), "..", "statistical_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stats_summary, f, indent=2)
    print(f"Saved statistical summary to: {out_path}")

    return stats_summary


if __name__ == "__main__":
    run_statistical_validation()

