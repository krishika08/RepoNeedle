"""
Comprehensive Evaluation Suite for Phase R5.
Evaluates Treatments A through H across Train, Validation, and Held-Out splits:
- A: R2 Treatment E (Authoritative Baseline Reference)
- B: R4 Treatment D (Best Dense Semantic Ranker)
- C: File-Level Retrieval Alone
- D: Function-Level Lexical Retrieval
- E: Function-Level Semantic Retrieval
- F: Change-Impact Retrieval (Typed Graph)
- G: Multi-Target Retrieval (Role-Aware MMR Selection)
- H: Combined Hierarchical Retrieval (File + Function + Impact + Multi-Target)

Generates:
- PER_QUERY_COMPARISON.jsonl (345 records)
- master_metrics.json
"""
import os
import sys
import json
import time
import numpy as np
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

r5_src = os.path.dirname(os.path.abspath(__file__))
r4_src = os.path.abspath(os.path.join(r5_src, "..", "..", "r4", "src"))
r2_src = os.path.abspath(os.path.join(r5_src, "..", "..", "r2", "src"))
root = os.path.abspath(os.path.join(r5_src, "..", "..", "..", ".."))

for p in [r5_src, r4_src, r2_src, root]:
    if p not in sys.path:
        sys.path.insert(0, p)

from split import load_data, TRAIN_REPOS, VAL_REPOS, HELD_OUT_REPOS
from ranker_r5 import R5Ranker, TREATMENTS


def compute_metrics(results: List[dict]) -> Dict[str, float]:
    total = len(results)
    if total == 0:
        return {}

    mrr_sum = 0.0
    hit1_count = 0
    r5_sum = 0.0
    r10_sum = 0.0
    r20_sum = 0.0
    latencies = []
    complete_coverage_count = 0

    for r in results:
        ranks = r["gold_ranks"]
        golds = r["gold_files"]
        if ranks:
            first_rank = ranks[0]
            mrr_sum += 1.0 / first_rank
            if first_rank == 1:
                hit1_count += 1

        r5_hits = sum(1 for rank in ranks if rank <= 5)
        r10_hits = sum(1 for rank in ranks if rank <= 10)
        r20_hits = sum(1 for rank in ranks if rank <= 20)

        r5_sum += (r5_hits / len(golds)) if golds else 0.0
        r10_sum += (r10_hits / len(golds)) if golds else 0.0
        r20_sum += (r20_hits / len(golds)) if golds else 0.0

        # Multi-target complete coverage: all gold targets recovered within top 20
        if golds and len(ranks) == len(golds) and all(rank <= 20 for rank in ranks):
            complete_coverage_count += 1

        latencies.append(r.get("latency_ms", 0.0))

    return {
        "mrr": mrr_sum / total,
        "hit1_pct": (hit1_count / total) * 100.0,
        "hit1_count": hit1_count,
        "recall_at_5": r5_sum / total,
        "recall_at_10": r10_sum / total,
        "recall_at_20": r20_sum / total,
        "complete_coverage_pct": (complete_coverage_count / total) * 100.0,
        "complete_coverage_count": complete_coverage_count,
        "total_queries": total,
        "latency_mean_ms": float(np.mean(latencies)) if latencies else 0.0,
        "latency_p50_ms": float(np.median(latencies)) if latencies else 0.0,
        "latency_p95_ms": float(np.percentile(latencies, 95)) if latencies else 0.0,
    }


def run_full_r5_evaluation():
    print("Loading data splits...")
    train_data, val_data, held_out_data = load_data()
    all_data = train_data + val_data + held_out_data
    split_map = {}
    for d in train_data:
        split_map[d["query_id"]] = "train"
    for d in val_data:
        split_map[d["query_id"]] = "val"
    for d in held_out_data:
        split_map[d["query_id"]] = "held_out"

    ranker = R5Ranker()
    treatments = ["A", "B", "C", "D", "E", "F", "G", "H"]

    per_query_records: Dict[str, dict] = {}
    treatment_split_metrics: Dict[str, Dict[str, dict]] = defaultdict(dict)

    for t_code in treatments:
        t_name = TREATMENTS[t_code]["name"]
        print(f"\nEvaluating Treatment {t_code}: {t_name}...")
        treatment_results = []

        for item in all_data:
            qid = item["query_id"]
            reranked, telemetry = ranker.rank(item["candidates"], item["query_text"], treatment=t_code)
            golds = set(item["gold_files"])

            gold_ranks = [c["rank"] for c in reranked if c["path"] in golds]
            top_candidates = [c["path"] for c in reranked[:5]]

            res_entry = {
                "query_id": qid,
                "repo": item["repo"],
                "split": split_map[qid],
                "task_type": item["task_type"],
                "gold_files": item["gold_files"],
                "gold_ranks": gold_ranks,
                "first_gold_rank": gold_ranks[0] if gold_ranks else None,
                "reciprocal_rank": (1.0 / gold_ranks[0]) if gold_ranks else 0.0,
                "top_5": top_candidates,
                "best_unit": reranked[0].get("best_unit") if reranked else None,
                "latency_ms": telemetry.get("latency_ms", 0.0),
            }
            treatment_results.append(res_entry)

            if qid not in per_query_records:
                per_query_records[qid] = {
                    "query_id": qid,
                    "repo": item["repo"],
                    "split": split_map[qid],
                    "task_type": item["task_type"],
                    "gold_files": item["gold_files"],
                    "treatments": {},
                }

            per_query_records[qid]["treatments"][t_code] = {
                "first_gold_rank": res_entry["first_gold_rank"],
                "reciprocal_rank": res_entry["reciprocal_rank"],
                "top_1": top_candidates[0] if top_candidates else None,
                "best_unit": res_entry["best_unit"],
                "latency_ms": res_entry["latency_ms"],
            }

        # Calculate metrics by split
        for s_name in ["train", "val", "held_out", "overall"]:
            if s_name == "overall":
                sub = treatment_results
            else:
                sub = [r for r in treatment_results if r["split"] == s_name]
            treatment_split_metrics[t_code][s_name] = compute_metrics(sub)

    # Print Summary Table
    print("\n" + "=" * 125)
    print(f"{'Code':<4} | {'Treatment Name':<38} | {'Val MRR':<9} | {'Val Hit@1':<10} | {'Val R@20':<9} | {'Val Cov':<8} | {'Train MRR':<10} | {'Held MRR':<9}")
    print("=" * 125)
    for t_code in treatments:
        t_name = TREATMENTS[t_code]["name"]
        vm = treatment_split_metrics[t_code]["val"]
        tm = treatment_split_metrics[t_code]["train"]
        hm = treatment_split_metrics[t_code]["held_out"]
        print(f"{t_code:<4} | {t_name:<38} | {vm['mrr']:<9.4f} | {vm['hit1_pct']:<9.2f}% | {vm['recall_at_20']:<9.4f} | {vm['complete_coverage_pct']:<7.1f}% | {tm['mrr']:<10.4f} | {hm['mrr']:<9.4f}")
    print("=" * 125)

    # Save outputs
    out_dir = os.path.join(os.path.dirname(__file__), "..")
    jsonl_path = os.path.join(out_dir, "PER_QUERY_COMPARISON.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for qid, record in per_query_records.items():
            f.write(json.dumps(record) + "\n")
    print(f"\nSaved PER_QUERY_COMPARISON.jsonl to: {jsonl_path} ({len(per_query_records)} records)")

    metrics_path = os.path.join(out_dir, "master_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(treatment_split_metrics, f, indent=2)
    print(f"Saved master_metrics.json to: {metrics_path}")

    return treatment_split_metrics


if __name__ == "__main__":
    run_full_r5_evaluation()
