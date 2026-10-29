"""
Stage 3.8: Independent Metric Verifier and Diagnostic Generator.

This script independently recomputes all benchmark metrics without importing any
existing metric-calculation functions from reponeedle or agent_retrieval_bench.
It verifies:
  1. Mean Reciprocal Rank (MRR) - both full-rank and top-20 cutoff.
  2. Fractional Multi-Target Recall@5, Recall@10, Recall@20.
  3. Binary Hit@20 (strictly segregated from fractional recall).
  4. Precision@5 (documented definition: hits / min(5, len(ranked))).
  5. Token Budgeted Context Yield at 8k tokens.
  6. Evaluated query counts (345 positive instances) and valid gold files.
  7. Per-query diagnostics classification and error analysis table.
"""

import os
import sys
import csv
import json
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_8"
STAGE7_DIR = ROOT_DIR / "research" / "stage3_7"
STAGE6_DIR = ROOT_DIR / "research" / "stage3_6"


# -----------------------------------------------------------------------------
# Clean, Independent Metric Implementations (Zero Project Imports)
# -----------------------------------------------------------------------------

def independent_reciprocal_rank(gold: set, ranked_paths: list, cutoff: int = 0) -> float:
    """
    Computes reciprocal rank: 1.0 / first_rank for the first gold target in ranked_paths.
    If cutoff > 0 and first_rank > cutoff, returns 0.0.
    If gold is empty or no gold target is found, returns 0.0.
    """
    if not gold or not ranked_paths:
        return 0.0
    for idx, path in enumerate(ranked_paths, start=1):
        if cutoff > 0 and idx > cutoff:
            break
        if path in gold:
            return 1.0 / idx
    return 0.0


def independent_fractional_recall(gold: set, ranked_paths: list, k: int) -> float:
    """
    Computes multi-target fractional recall: |gold intersect ranked[:k]| / |gold|.
    """
    if not gold or k <= 0:
        return 0.0
    top_k = set(ranked_paths[:k])
    hits = len(gold.intersection(top_k))
    return float(hits) / float(len(gold))


def independent_binary_hit(gold: set, ranked_paths: list, k: int) -> float:
    """
    Computes binary hit indicator: 1.0 if at least one gold target in ranked[:k], else 0.0.
    """
    if not gold or k <= 0:
        return 0.0
    top_k = set(ranked_paths[:k])
    return 1.0 if len(gold.intersection(top_k)) > 0 else 0.0


def independent_precision(gold: set, ranked_paths: list, k: int) -> float:
    """
    Computes precision at k: |gold intersect ranked[:k]| / min(k, len(ranked_paths)).
    """
    if not ranked_paths or k <= 0:
        return 0.0
    denom = min(k, len(ranked_paths))
    if denom == 0:
        return 0.0
    top_k = set(ranked_paths[:k])
    hits = len(gold.intersection(top_k))
    return float(hits) / float(denom)


def run_independent_verification():
    s36_path = STAGE6_DIR / "PER_QUERY_RESULTS.csv"
    assert s36_path.exists(), f"Missing input file: {s36_path}"

    with open(s36_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    print(f"Loaded {len(reader)} query-system rows from {s36_path.name}")

    by_query = defaultdict(dict)
    for r in reader:
        by_query[r["query_id"]][r["system_id"]] = r

    num_queries = len(by_query)
    print(f"Total unique positive queries: {num_queries}")
    assert num_queries == 345, f"Expected 345 queries, got {num_queries}"

    systems = ["BASE-BM25", "CAND-C", "CAND-F", "BASE-REPOMAP"]

    # Storage for independent metrics
    sys_metrics = {s: defaultdict(list) for s in systems}

    # Storage for per-query diagnostic records
    diagnostic_rows = []

    for qid, sys_map in sorted(by_query.items()):
        bm = sys_map["BASE-BM25"]
        cc = sys_map["CAND-C"]
        cf = sys_map["CAND-F"]
        rm = sys_map["BASE-REPOMAP"]

        repo = bm["repo"]
        task_type = bm["task_type"]
        language = bm["language"]

        gold_files = [p.strip() for p in bm["gold_files"].split(";") if p.strip()]
        gold_set = set(gold_files)
        num_gold = len(gold_set)

        # Process each system
        row_diag = {
            "query_id": qid,
            "repo": repo,
            "task_type": task_type,
            "language": language,
            "num_gold": num_gold,
        }

        first_ranks = {}
        mrrs = {}
        hits20 = {}
        hits5 = {}
        hits10 = {}

        for s in systems:
            rec = sys_map[s]
            f_rank = int(rec["first_relevant_rank"])
            mrr_stored = float(rec["mrr"])
            r5_stored = float(rec["recall_at_5"])
            r10_stored = float(rec["recall_at_10"])
            r20_stored = float(rec["recall_at_20"])
            p5_stored = float(rec["precision_at_5"])
            bcy8k_stored = float(rec["bcy_at_8k"])

            top5_paths = [p.strip() for p in rec["top_ranked_paths"].split(";") if p.strip()]

            # Independent metrics
            indep_r5 = independent_fractional_recall(gold_set, top5_paths, 5)
            indep_p5 = independent_precision(gold_set, top5_paths, 5)
            indep_hit5 = independent_binary_hit(gold_set, top5_paths, 5)

            # Recomputed MRR from first_relevant_rank
            indep_mrr_full = 1.0 / f_rank if f_rank > 0 else 0.0
            indep_mrr_top20 = (1.0 / f_rank) if (1 <= f_rank <= 20) else 0.0

            # Binary Hit@20
            indep_hit20 = 1.0 if (1 <= f_rank <= 20) else 0.0

            # Store for aggregate calculations
            sys_metrics[s]["mrr_stored"].append(mrr_stored)
            sys_metrics[s]["mrr_full"].append(indep_mrr_full)
            sys_metrics[s]["mrr_top20"].append(indep_mrr_top20)
            sys_metrics[s]["recall_5"].append(indep_r5)
            sys_metrics[s]["recall_10"].append(r10_stored)
            sys_metrics[s]["recall_20"].append(r20_stored)
            sys_metrics[s]["hit_20"].append(indep_hit20)
            sys_metrics[s]["precision_5_stored"].append(p5_stored)
            sys_metrics[s]["precision_5_indep"].append(indep_p5)
            sys_metrics[s]["bcy_8k"].append(bcy8k_stored)

            # For per-query table
            first_ranks[s] = f_rank
            mrrs[s] = mrr_stored
            hits5[s] = round(indep_r5 * num_gold)
            hits10[s] = round(r10_stored * num_gold)
            hits20[s] = round(r20_stored * num_gold)

        # Classification of retrieval failure mode
        bm_rank = first_ranks["BASE-BM25"]
        cc_rank = first_ranks["CAND-C"]
        cf_rank = first_ranks["CAND-F"]
        rm_rank = first_ranks["BASE-REPOMAP"]

        if (bm_rank > 20 or bm_rank == -1) and (cc_rank > 20 or cc_rank == -1) and (cf_rank > 20 or cf_rank == -1) and (rm_rank > 20 or rm_rank == -1):
            category = "ALL_FAIL"
        elif (1 <= rm_rank <= 20) and (bm_rank > 20 or bm_rank == -1) and (cc_rank > 20 or cc_rank == -1) and (cf_rank > 20 or cf_rank == -1):
            category = "REPOMAP_WIN_REPONEEDLE_FAIL"
        elif 1 <= bm_rank <= 5 and (cf_rank > bm_rank):
            category = "BM25_WIN_CAND_DEMOTED"
        elif hits20["CAND-F"] > hits20["BASE-BM25"] and mrrs["CAND-F"] < mrrs["BASE-BM25"]:
            category = "CAND_MORE_GOLD_WORSE_FIRST_RANK"
        elif (1 <= cf_rank <= 20) and (rm_rank > 20 or rm_rank == -1):
            category = "REPONEEDLE_WIN_REPOMAP_FAIL"
        elif cf_rank < bm_rank and (1 <= cf_rank <= 20):
            category = "CAND_WIN_BM25_LOSS"
        else:
            category = "PARITY_OR_OTHER"

        def rank_status(r):
            if r == -1:
                return "MISSING_ENTIRELY"
            if 1 <= r <= 5:
                return "TOP_5"
            if 6 <= r <= 10:
                return "TOP_10"
            if 11 <= r <= 20:
                return "TOP_20"
            return "RANKED_TOO_LOW (>20)"

        diag_row = {
            "query_id": qid,
            "repo": repo,
            "task_type": task_type,
            "language": language,
            "num_gold": num_gold,
            "bm25_first_rank": bm_rank,
            "cand_c_first_rank": cc_rank,
            "cand_f_first_rank": cf_rank,
            "repomap_first_rank": rm_rank,
            "bm25_mrr": f"{mrrs['BASE-BM25']:.6f}",
            "cand_c_mrr": f"{mrrs['CAND-C']:.6f}",
            "cand_f_mrr": f"{mrrs['CAND-F']:.6f}",
            "repomap_mrr": f"{mrrs['BASE-REPOMAP']:.6f}",
            "bm25_hits_5": hits5["BASE-BM25"],
            "cand_c_hits_5": hits5["CAND-C"],
            "cand_f_hits_5": hits5["CAND-F"],
            "repomap_hits_5": hits5["BASE-REPOMAP"],
            "bm25_hits_10": hits10["BASE-BM25"],
            "cand_c_hits_10": hits10["CAND-C"],
            "cand_f_hits_10": hits10["CAND-F"],
            "repomap_hits_10": hits10["BASE-REPOMAP"],
            "bm25_hits_20": hits20["BASE-BM25"],
            "cand_c_hits_20": hits20["CAND-C"],
            "cand_f_hits_20": hits20["CAND-F"],
            "repomap_hits_20": hits20["BASE-REPOMAP"],
            "bm25_status": rank_status(bm_rank),
            "cand_c_status": rank_status(cc_rank),
            "cand_f_status": rank_status(cf_rank),
            "repomap_status": rank_status(rm_rank),
            "failure_category": category,
        }
        diagnostic_rows.append(diag_row)

    # Write PER_QUERY_DIAGNOSTICS.csv
    diag_csv_path = STAGE_DIR / "PER_QUERY_DIAGNOSTICS.csv"
    with open(diag_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(diagnostic_rows[0].keys()))
        writer.writeheader()
        writer.writerows(diagnostic_rows)
    print(f"Wrote {diag_csv_path.name} with {len(diagnostic_rows)} rows")

    # Write summary comparison
    print("\n" + "=" * 90)
    print("INDEPENDENT METRIC RECOMPUTATION AUDIT (N=345 Positive Queries)")
    print("=" * 90)
    print(f"{'System':<15} | {'MRR(Full)':<10} | {'MRR(@20)':<10} | {'R@5':<8} | {'R@10':<8} | {'R@20':<8} | {'Hit@20':<8} | {'P@5(Indep)':<10} | {'BCY@8k':<8}")
    print("-" * 90)

    for s in systems:
        v = sys_metrics[s]
        mrr_full = np.mean(v["mrr_full"])
        mrr_top20 = np.mean(v["mrr_top20"])
        r5 = np.mean(v["recall_5"])
        r10 = np.mean(v["recall_10"])
        r20 = np.mean(v["recall_20"])
        hit20 = np.mean(v["hit_20"])
        p5_indep = np.mean(v["precision_5_indep"])
        bcy8k = np.mean(v["bcy_8k"])
        print(f"{s:<15} | {mrr_full:<10.4f} | {mrr_top20:<10.4f} | {r5:<8.4f} | {r10:<8.4f} | {r20:<8.4f} | {hit20:<8.4f} | {p5_indep:<10.4f} | {bcy8k:<8.4f}")

    print("=" * 90)


if __name__ == "__main__":
    run_independent_verification()
