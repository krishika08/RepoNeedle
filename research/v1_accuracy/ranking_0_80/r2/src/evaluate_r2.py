"""
Comprehensive Evaluation Suite for Mission 0.80+ Phase R2.
Evaluates Treatments A through H on Training and Validation sets with full ablations and statistical tests.
"""
import copy
import json
import os
import time
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
from split import load_data, TRAIN_REPOS, VAL_REPOS, HELD_OUT_REPOS
from ranker_r2 import R2Ranker, TREATMENTS

def compute_metrics(eval_records: List[dict]) -> dict:
    """Compute standard IR metrics from evaluated query records."""
    if not eval_records:
        return {}

    n = len(eval_records)
    mrrs = [r["rr"] for r in eval_records]
    r1_hits = sum(1 for r in eval_records if r["first_gold_rank"] == 1)
    recalls_5 = [r["recall@5"] for r in eval_records]
    recalls_10 = [r["recall@10"] for r in eval_records]
    recalls_20 = [r["recall@20"] for r in eval_records]
    total_recalls = [r["total_gold_recall"] for r in eval_records]
    seed_self_retrievals = sum(1 for r in eval_records if r["rank1_is_seed"])
    rank1_displacements = sum(1 for r in eval_records if r["first_gold_rank"] != 1)
    latencies = [r["latency_ms"] for r in eval_records]

    return {
        "count": n,
        "mrr": float(np.mean(mrrs)),
        "mrr_std": float(np.std(mrrs)),
        "hit@1": float(r1_hits / n),
        "hit@1_count": r1_hits,
        "recall@5": float(np.mean(recalls_5)),
        "recall@10": float(np.mean(recalls_10)),
        "recall@20": float(np.mean(recalls_20)),
        "total_gold_recall": float(np.mean(total_recalls)),
        "rank1_displacement_rate": float(rank1_displacements / n),
        "seed_self_retrieval_rate": float(seed_self_retrievals / n),
        "seed_self_retrieval_count": seed_self_retrievals,
        "latency_p50_ms": float(np.median(latencies)),
        "latency_p95_ms": float(np.percentile(latencies, 95)),
        "latency_mean_ms": float(np.mean(latencies)),
    }

def evaluate_dataset(
    dataset: List[dict],
    treatment: str,
    config: Optional[dict] = None
) -> Tuple[dict, List[dict]]:
    """Evaluate a specific dataset (train/val) on a specific treatment."""
    ranker = R2Ranker(config)
    eval_records = []

    for item in dataset:
        qid = item["query_id"]
        gold_files = set(item["gold_files"])
        num_gold = len(gold_files)
        query_text = item["query_text"]
        cands = item["candidates"]

        reranked, telem = ranker.rank(cands, query_text, treatment=treatment)
        latency = telem.get("latency_ms", 0.0)

        # Identify ranks of gold files
        gold_ranks = []
        for c in reranked:
            if c["path"] in gold_files:
                gold_ranks.append(c["rank"])

        first_gold_rank = min(gold_ranks) if gold_ranks else None
        rr = 1.0 / first_gold_rank if first_gold_rank else 0.0
        r5 = sum(1 for r in gold_ranks if r <= 5) / num_gold if num_gold else 0.0
        r10 = sum(1 for r in gold_ranks if r <= 10) / num_gold if num_gold else 0.0
        r20 = sum(1 for r in gold_ranks if r <= 20) / num_gold if num_gold else 0.0
        tot_rec = len(gold_ranks) / num_gold if num_gold else 0.0

        top1_path = reranked[0]["path"] if reranked else ""
        seeds = set(telem.get("seeds", []))
        rank1_is_seed = (top1_path in seeds and top1_path not in gold_files)

        record = {
            "query_id": qid,
            "repo": item["repo"],
            "task_type": item["task_type"],
            "gold_files": item["gold_files"],
            "treatment": treatment,
            "first_gold_rank": first_gold_rank,
            "rr": rr,
            "recall@5": r5,
            "recall@10": r10,
            "recall@20": r20,
            "total_gold_recall": tot_rec,
            "top1_path": top1_path,
            "rank1_is_seed": rank1_is_seed,
            "latency_ms": latency,
            "telem": telem,
        }
        eval_records.append(record)

    summary = compute_metrics(eval_records)
    return summary, eval_records

def run_experiment_matrix():
    print("=== LOADING SPLITS ===")
    train_data, val_data, held_out_data = load_data()
    print(f"Train: {len(train_data)} | Val: {len(val_data)} | Held-Out: {len(held_out_data)}")

    treatments = ["A", "B", "C", "D", "E", "F", "G", "H"]
    
    train_results = {}
    val_results = {}
    per_query_records_train = defaultdict(dict)
    per_query_records_val = defaultdict(dict)

    print("\n=== RUNNING EXPERIMENT MATRIX (TREATMENTS A..H) ===")
    
    for t_code in treatments:
        t_name = TREATMENTS[t_code]["name"]
        print(f"\nEvaluating Treatment {t_code}: {t_name}...")
        
        # Train
        train_sum, train_recs = evaluate_dataset(train_data, t_code)
        train_results[t_code] = train_sum
        for r in train_recs:
            per_query_records_train[r["query_id"]][t_code] = r
            
        # Val
        val_sum, val_recs = evaluate_dataset(val_data, t_code)
        val_results[t_code] = val_sum
        for r in val_recs:
            per_query_records_val[r["query_id"]][t_code] = r

        print(f"  Train: MRR = {train_sum['mrr']:.4f} | Hit@1 = {train_sum['hit@1']*100:.2f}% | R@20 = {train_sum['recall@20']:.4f} | Seed Trap = {train_sum['seed_self_retrieval_count']}")
        print(f"  Val:   MRR = {val_sum['mrr']:.4f} | Hit@1 = {val_sum['hit@1']*100:.2f}% | R@20 = {val_sum['recall@20']:.4f} | Seed Trap = {val_sum['seed_self_retrieval_count']}")

    return train_data, val_data, train_results, val_results, per_query_records_train, per_query_records_val

if __name__ == "__main__":
    run_experiment_matrix()
