"""
Statistical Validation & Per-Query Comparison Generator for Phase R2.
Computes 95% bootstrap confidence intervals, paired permutation p-values,
per-task breakdowns, and exports PER_QUERY_COMPARISON.jsonl.
"""
import copy
import json
import os
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
from split import load_data
from ranker_r2 import R2Ranker, TREATMENTS
from evaluate_r2 import evaluate_dataset, compute_metrics

def bootstrap_ci(diffs: np.ndarray, n_boot: int = 10000, seed: int = 42) -> Tuple[float, float, float]:
    """Computes 95% percentile bootstrap confidence interval and non-positive proportion."""
    rng = np.random.default_rng(seed)
    n = len(diffs)
    boot_means = rng.choice(diffs, size=(n_boot, n), replace=True).mean(axis=1)
    ci_low = float(np.percentile(boot_means, 2.5))
    ci_high = float(np.percentile(boot_means, 97.5))
    p_non_pos = float(np.mean(boot_means <= 0.0))
    return ci_low, ci_high, p_non_pos

def paired_permutation_test(a: np.ndarray, b: np.ndarray, n_perm: int = 10000, seed: int = 42) -> float:
    """Computes two-tailed paired permutation p-value."""
    rng = np.random.default_rng(seed)
    diff = a - b
    obs_diff = np.abs(np.mean(diff))
    n = len(diff)
    signs = rng.choice([-1, 1], size=(n_perm, n))
    perm_diffs = np.abs(np.mean(signs * diff, axis=1))
    p_val = float(np.mean(perm_diffs >= obs_diff))
    return p_val

def run_full_statistical_validation():
    train_data, val_data, held_out_data = load_data()
    print("=== STATISTICAL VALIDATION & PER-QUERY EXPORT ===")

    # Configurations:
    # Selected best config for Treatment E:
    cfg_e = {"sfs_demotion_factor": 0.05, "tip_boost_weight": 1.5, "tip_threshold": 0.5}
    # Selected best config for Treatment H:
    cfg_h = {"sfs_demotion_factor": 0.05, "tip_boost_weight": 1.5, "sms_weight": 0.1}

    # Evaluate all treatments on Train and Val
    train_evals = {}
    val_evals = {}
    all_treatments = ["A", "B", "C", "D", "E", "F", "G", "H"]

    for t in all_treatments:
        cfg = cfg_h if t in ["F", "H"] else (cfg_e if t in ["B", "C", "E"] else None)
        sum_tr, recs_tr = evaluate_dataset(train_data, t, cfg)
        sum_val, recs_val = evaluate_dataset(val_data, t, cfg)
        train_evals[t] = (sum_tr, recs_tr)
        val_evals[t] = (sum_val, recs_val)

    # 1. Statistical Significance of Treatments vs Treatment A (Baseline)
    print("\n--- Statistical Significance vs Baseline M1 (Treatment A) ---")
    stat_report = {}
    
    base_tr_rr = np.array([r["rr"] for r in train_evals["A"][1]])
    base_val_rr = np.array([r["rr"] for r in val_evals["A"][1]])

    for split_name, base_rr, evals in [("Train", base_tr_rr, train_evals), ("Validation", base_val_rr, val_evals)]:
        print(f"\n{split_name} Set Significance:")
        stat_report[split_name] = {}
        for t in ["B", "C", "D", "E", "F", "G", "H"]:
            sum_t, recs_t = evals[t]
            t_rr = np.array([r["rr"] for r in recs_t])
            diff = t_rr - base_rr
            delta_mrr = float(np.mean(diff))
            rel_delta = float(delta_mrr / np.mean(base_rr) * 100) if np.mean(base_rr) > 0 else 0.0
            
            ci_low, ci_high, p_non_pos = bootstrap_ci(diff)
            perm_p = paired_permutation_test(t_rr, base_rr)
            
            stat_report[split_name][t] = {
                "name": TREATMENTS[t]["name"],
                "mrr": sum_t["mrr"],
                "delta_mrr": delta_mrr,
                "rel_delta_pct": rel_delta,
                "ci_95": [ci_low, ci_high],
                "p_non_pos": p_non_pos,
                "permutation_p": perm_p,
                "hit@1": sum_t["hit@1"],
                "recall@20": sum_t["recall@20"],
            }
            print(f"  Treatment {t:<2} ({TREATMENTS[t]['name']:<24}): MRR={sum_t['mrr']:.4f} (Delta={delta_mrr:+.4f}, {rel_delta:+.1f}%) | 95% CI=[{ci_low:+.4f}, {ci_high:+.4f}] | p={perm_p:.4f}")

    # 2. Per-Task Type Breakdown for Baseline vs Treatment E and H
    print("\n--- Per-Task Breakdown (Validation Set) ---")
    val_by_task = defaultdict(lambda: defaultdict(list))
    for t in ["A", "E", "H"]:
        for r in val_evals[t][1]:
            val_by_task[r["task_type"]][t].append(r["rr"])

    task_summary = {}
    for task, t_data in sorted(val_by_task.items()):
        cnt = len(t_data["A"])
        mrr_a = np.mean(t_data["A"])
        mrr_e = np.mean(t_data["E"])
        mrr_h = np.mean(t_data["H"])
        task_summary[task] = {
            "count": cnt,
            "mrr_A": float(mrr_a),
            "mrr_E": float(mrr_e),
            "mrr_H": float(mrr_h),
            "delta_E": float(mrr_e - mrr_a),
            "delta_H": float(mrr_h - mrr_a),
        }
        print(f"  {task:<18} (n={cnt:<2}): Base M1 = {mrr_a:.4f} | Treatment E = {mrr_e:.4f} ({mrr_e-mrr_a:+.4f}) | Treatment H = {mrr_h:.4f} ({mrr_h-mrr_a:+.4f})")

    # 3. Export PER_QUERY_COMPARISON.jsonl
    out_dir = "research/v1_accuracy/ranking_0_80/r2"
    os.makedirs(out_dir, exist_ok=True)
    jsonl_path = os.path.join(out_dir, "PER_QUERY_COMPARISON.jsonl")

    total_exported = 0
    with open(jsonl_path, "w", encoding="utf-8") as f:
        # Export Train records
        for i in range(len(train_data)):
            qid = train_data[i]["query_id"]
            row = {
                "query_id": qid,
                "split": "train",
                "repo": train_data[i]["repo"],
                "task_type": train_data[i]["task_type"],
                "gold_files": train_data[i]["gold_files"],
                "treatments": {
                    t: {
                        "rank": train_evals[t][1][i]["first_gold_rank"],
                        "rr": train_evals[t][1][i]["rr"],
                        "r20": train_evals[t][1][i]["recall@20"],
                        "top1": train_evals[t][1][i]["top1_path"],
                        "rank1_is_seed": train_evals[t][1][i]["rank1_is_seed"],
                    } for t in all_treatments
                }
            }
            f.write(json.dumps(row) + "\n")
            total_exported += 1

        # Export Val records
        for i in range(len(val_data)):
            qid = val_data[i]["query_id"]
            row = {
                "query_id": qid,
                "split": "val",
                "repo": val_data[i]["repo"],
                "task_type": val_data[i]["task_type"],
                "gold_files": val_data[i]["gold_files"],
                "treatments": {
                    t: {
                        "rank": val_evals[t][1][i]["first_gold_rank"],
                        "rr": val_evals[t][1][i]["rr"],
                        "r20": val_evals[t][1][i]["recall@20"],
                        "top1": val_evals[t][1][i]["top1_path"],
                        "rank1_is_seed": val_evals[t][1][i]["rank1_is_seed"],
                    } for t in all_treatments
                }
            }
            f.write(json.dumps(row) + "\n")
            total_exported += 1

    print(f"\nExported {total_exported} query records to {jsonl_path}")

    # Export statistical summary to json for reporting
    with open(os.path.join(out_dir, "statistical_summary.json"), "w", encoding="utf-8") as f:
        json.dump({
            "statistical_significance": stat_report,
            "task_summary_val": task_summary,
            "train_metrics": {t: train_evals[t][0] for t in all_treatments},
            "val_metrics": {t: val_evals[t][0] for t in all_treatments},
        }, f, indent=2)

    return stat_report, task_summary

if __name__ == "__main__":
    run_full_statistical_validation()
