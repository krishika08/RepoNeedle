"""
Stage 3.6: Rigorous Paired Statistical Analysis Engine.
Reads research/stage3_6/PER_QUERY_RESULTS.csv and computes:
  - System performance summaries
  - Paired win / tie / loss counts
  - Repository-clustered bootstrap 95% confidence intervals (B=10,000, seed=42)
  - Wilcoxon signed-rank and paired t-tests
  - Per-task breakdowns (code2test, comment2context, trace2code, edit2ripple)
  - Per-language breakdowns (Python, Rust, Go, TypeScript/JS, etc.)

Generates:
  - research/stage3_6/PAIRED_STATISTICS.md
"""

import sys
import os
import csv
from pathlib import Path
from collections import defaultdict
import numpy as np
import scipy.stats as stats

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"


def run_paired_statistics():
    csv_path = ROOT_DIR / "research" / "stage3_6" / "PER_QUERY_RESULTS.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist yet.")
        return

    print("Loading PER_QUERY_RESULTS.csv for paired statistical analysis...")
    reader = csv.DictReader(open(csv_path, encoding="utf-8"))
    rows = list(reader)
    print(f"Loaded {len(rows)} per-query system records.")

    # Group by system and query_id
    by_sys = defaultdict(dict)
    all_queries = set()
    repo_by_query = {}
    task_by_query = {}
    lang_by_query = {}

    for r in rows:
        qid = r["query_id"]
        sid = r["system_id"]
        all_queries.add(qid)
        repo_by_query[qid] = r["repo"]
        task_by_query[qid] = r["task_type"]
        lang_by_query[qid] = r["language"]
        by_sys[sid][qid] = {
            "mrr": float(r["mrr"]),
            "r1": float(r["recall_at_1"]),
            "r5": float(r["recall_at_5"]),
            "r10": float(r["recall_at_10"]),
            "r20": float(r["recall_at_20"]),
            "p5": float(r["precision_at_5"]),
            "p10": float(r["precision_at_10"]),
            "p20": float(r["precision_at_20"]),
            "bcy_4k": float(r["bcy_at_4k"]),
            "bcy_8k": float(r["bcy_at_8k"]),
            "bcy_16k": float(r["bcy_at_16k"]),
            "lat": float(r["latency_ms"]),
        }

    q_list = sorted(list(all_queries))
    n_queries = len(q_list)
    print(f"Total unique queries evaluated: {n_queries}")

    systems = ["BASE-BM25", "CAND-C", "CAND-F", "BASE-REPOMAP"]

    # 1. Macro summaries
    sys_summary = {}
    for s in systems:
        metrics = {
            "mrr": [by_sys[s][q]["mrr"] for q in q_list],
            "r1": [by_sys[s][q]["r1"] for q in q_list],
            "r5": [by_sys[s][q]["r5"] for q in q_list],
            "r10": [by_sys[s][q]["r10"] for q in q_list],
            "r20": [by_sys[s][q]["r20"] for q in q_list],
            "p5": [by_sys[s][q]["p5"] for q in q_list],
            "p10": [by_sys[s][q]["p10"] for q in q_list],
            "p20": [by_sys[s][q]["p20"] for q in q_list],
            "bcy_4k": [by_sys[s][q]["bcy_4k"] for q in q_list],
            "bcy_8k": [by_sys[s][q]["bcy_8k"] for q in q_list],
            "bcy_16k": [by_sys[s][q]["bcy_16k"] for q in q_list],
            "lat": [by_sys[s][q]["lat"] for q in q_list],
        }
        sys_summary[s] = {
            "mrr": float(np.mean(metrics["mrr"])),
            "r1": float(np.mean(metrics["r1"])),
            "r5": float(np.mean(metrics["r5"])),
            "r10": float(np.mean(metrics["r10"])),
            "r20": float(np.mean(metrics["r20"])),
            "p5": float(np.mean(metrics["p5"])),
            "p10": float(np.mean(metrics["p10"])),
            "p20": float(np.mean(metrics["p20"])),
            "bcy_4k": float(np.mean(metrics["bcy_4k"])),
            "bcy_8k": float(np.mean(metrics["bcy_8k"])),
            "bcy_16k": float(np.mean(metrics["bcy_16k"])),
            "lat_mean": float(np.mean(metrics["lat"])),
            "lat_p50": float(np.median(metrics["lat"])),
            "lat_p95": float(np.percentile(metrics["lat"], 95)),
        }

    # 2. Clustered Bootstrap by Repository
    # Build repository cluster map
    repo_clusters = defaultdict(list)
    for idx, q in enumerate(q_list):
        repo_clusters[repo_by_query[q]].append(idx)

    unique_repos = list(repo_clusters.keys())
    n_repos = len(unique_repos)
    print(f"Clustering bootstrap across {n_repos} distinct repository environments...")

    rng = np.random.default_rng(42)
    B = 10000

    comparisons = [
        ("CAND-C", "CAND-F", "Candidate C vs. Candidate F"),
        ("BASE-BM25", "CAND-F", "BM25 Baseline vs. Candidate F"),
        ("BASE-REPOMAP", "CAND-F", "RepoMap Baseline vs. Candidate F"),
    ]

    paired_stats_results = {}

    for s_base, s_target, comp_name in comparisons:
        arr_base_mrr = np.array([by_sys[s_base][q]["mrr"] for q in q_list])
        arr_target_mrr = np.array([by_sys[s_target][q]["mrr"] for q in q_list])
        diff_mrr = arr_target_mrr - arr_base_mrr

        arr_base_r20 = np.array([by_sys[s_base][q]["r20"] for q in q_list])
        arr_target_r20 = np.array([by_sys[s_target][q]["r20"] for q in q_list])
        diff_r20 = arr_target_r20 - arr_base_r20

        arr_base_bcy = np.array([by_sys[s_base][q]["bcy_8k"] for q in q_list])
        arr_target_bcy = np.array([by_sys[s_target][q]["bcy_8k"] for q in q_list])
        diff_bcy = arr_target_bcy - arr_base_bcy

        # Win / Tie / Loss on MRR
        wins_mrr = int(np.sum(diff_mrr > 1e-5))
        losses_mrr = int(np.sum(diff_mrr < -1e-5))
        ties_mrr = n_queries - wins_mrr - losses_mrr

        # Win / Tie / Loss on R@20
        wins_r20 = int(np.sum(diff_r20 > 1e-5))
        losses_r20 = int(np.sum(diff_r20 < -1e-5))
        ties_r20 = n_queries - wins_r20 - losses_r20

        # Win / Tie / Loss on BCY@8k
        wins_bcy = int(np.sum(diff_bcy > 1e-5))
        losses_bcy = int(np.sum(diff_bcy < -1e-5))
        ties_bcy = n_queries - wins_bcy - losses_bcy

        # Statistical tests
        t_mrr = stats.ttest_rel(arr_target_mrr, arr_base_mrr)
        # Wilcoxon signed rank test (handle zeros)
        nonzero_diff_mrr = diff_mrr[np.abs(diff_mrr) > 1e-7]
        if len(nonzero_diff_mrr) > 0:
            wilc_mrr = stats.wilcoxon(nonzero_diff_mrr)
            w_pval_mrr = wilc_mrr.pvalue
            w_stat_mrr = wilc_mrr.statistic
        else:
            w_pval_mrr = 1.0
            w_stat_mrr = 0.0

        t_r20 = stats.ttest_rel(arr_target_r20, arr_base_r20)
        nonzero_diff_r20 = diff_r20[np.abs(diff_r20) > 1e-7]
        if len(nonzero_diff_r20) > 0:
            wilc_r20 = stats.wilcoxon(nonzero_diff_r20)
            w_pval_r20 = wilc_r20.pvalue
        else:
            w_pval_r20 = 1.0

        # Clustered Bootstrap iterations
        boot_diff_mrr = []
        boot_diff_r20 = []
        boot_diff_bcy = []

        for _ in range(B):
            sampled_repos = rng.choice(unique_repos, size=n_repos, replace=True)
            sampled_indices = []
            for r in sampled_repos:
                sampled_indices.extend(repo_clusters[r])
            
            boot_diff_mrr.append(np.mean(diff_mrr[sampled_indices]))
            boot_diff_r20.append(np.mean(diff_r20[sampled_indices]))
            boot_diff_bcy.append(np.mean(diff_bcy[sampled_indices]))

        ci_mrr = (float(np.percentile(boot_diff_mrr, 2.5)), float(np.percentile(boot_diff_mrr, 97.5)))
        ci_r20 = (float(np.percentile(boot_diff_r20, 2.5)), float(np.percentile(boot_diff_r20, 97.5)))
        ci_bcy = (float(np.percentile(boot_diff_bcy, 2.5)), float(np.percentile(boot_diff_bcy, 97.5)))

        paired_stats_results[comp_name] = {
            "base": s_base,
            "target": s_target,
            "mean_delta_mrr": float(np.mean(diff_mrr)),
            "ci_mrr": ci_mrr,
            "t_stat_mrr": float(t_mrr.statistic) if not np.isnan(t_mrr.statistic) else 0.0,
            "t_pval_mrr": float(t_mrr.pvalue) if not np.isnan(t_mrr.pvalue) else 1.0,
            "w_pval_mrr": float(w_pval_mrr),
            "wins_mrr": wins_mrr,
            "ties_mrr": ties_mrr,
            "losses_mrr": losses_mrr,
            "mean_delta_r20": float(np.mean(diff_r20)),
            "ci_r20": ci_r20,
            "t_stat_r20": float(t_r20.statistic) if not np.isnan(t_r20.statistic) else 0.0,
            "t_pval_r20": float(t_r20.pvalue) if not np.isnan(t_r20.pvalue) else 1.0,
            "w_pval_r20": float(w_pval_r20),
            "wins_r20": wins_r20,
            "ties_r20": ties_r20,
            "losses_r20": losses_r20,
            "mean_delta_bcy": float(np.mean(diff_bcy)),
            "ci_bcy": ci_bcy,
            "wins_bcy": wins_bcy,
            "ties_bcy": ties_bcy,
            "losses_bcy": losses_bcy,
        }

    # 3. Per-Task Breakdown
    tasks = sorted(list(set(task_by_query.values())))
    task_breakdown = defaultdict(dict)
    for t in tasks:
        t_indices = [idx for idx, q in enumerate(q_list) if task_by_query[q] == t]
        for s in systems:
            t_mrr = [by_sys[s][q_list[i]]["mrr"] for i in t_indices]
            t_r20 = [by_sys[s][q_list[i]]["r20"] for i in t_indices]
            t_bcy = [by_sys[s][q_list[i]]["bcy_8k"] for i in t_indices]
            task_breakdown[t][s] = {
                "count": len(t_indices),
                "mrr": float(np.mean(t_mrr)),
                "r20": float(np.mean(t_r20)),
                "bcy": float(np.mean(t_bcy)),
            }

    # 4. Per-Language Breakdown
    languages = sorted(list(set(lang_by_query.values())))
    lang_breakdown = defaultdict(dict)
    for l in languages:
        l_indices = [idx for idx, q in enumerate(q_list) if lang_by_query[q] == l]
        for s in systems:
            l_mrr = [by_sys[s][q_list[i]]["mrr"] for i in l_indices]
            l_r20 = [by_sys[s][q_list[i]]["r20"] for i in l_indices]
            l_bcy = [by_sys[s][q_list[i]]["bcy_8k"] for i in l_indices]
            lang_breakdown[l][s] = {
                "count": len(l_indices),
                "mrr": float(np.mean(l_mrr)),
                "r20": float(np.mean(l_r20)),
                "bcy": float(np.mean(l_bcy)),
            }

    # Write PAIRED_STATISTICS.md
    md = [
        "# REPONEEDLE STAGE 3.6: PAIRED STATISTICAL ANALYSIS & AUDIT REPORT",
        "",
        "**Document ID**: `STAGE3.6-STAT-001`  ",
        "**Date**: October 2026  ",
        "**Benchmark Scope**: ARB v2 Full Positive Benchmark ($N=345$) across 4 Systems  ",
        "**Statistical Protocol**: 10,000 Clustered Bootstrap Resamples (Cluster Unit: Repository Environment, Seed: 42) + Wilcoxon Signed-Rank Test  ",
        "",
        "---",
        "",
        "## 1. COMPREHENSIVE BENCHMARK SUMMARY (N=345 POSITIVE QUERIES)",
        "",
        "| System ID | MRR | Recall@1 | Recall@5 | Recall@10 | Recall@20 | Precision@5 | Precision@10 | Precision@20 | BCY@4k | BCY@8k | BCY@16k | Mean Latency (ms) | Median Latency (ms) | p95 Latency (ms) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for s in systems:
        sm = sys_summary[s]
        md.append(
            f"| **`{s}`** | {sm['mrr']:.4f} | {sm['r1']:.4f} | {sm['r5']:.4f} | {sm['r10']:.4f} | {sm['r20']:.4f} | "
            f"{sm['p5']:.4f} | {sm['p10']:.4f} | {sm['p20']:.4f} | {sm['bcy_4k']:.4f} | {sm['bcy_8k']:.4f} | {sm['bcy_16k']:.4f} | "
            f"{sm['lat_mean']:.2f} ms | {sm['lat_p50']:.2f} ms | {sm['lat_p95']:.2f} ms |"
        )

    md.extend([
        "",
        "---",
        "",
        "## 2. PAIRED COMPARISONS & HYPOTHESIS TESTING",
        "",
    ])

    for comp_name, res in paired_stats_results.items():
        sig_mrr = "Statistically Significant ($p < 0.05$)" if res['w_pval_mrr'] < 0.05 else "Not Statistically Significant ($p \\ge 0.05$)"
        sig_r20 = "Statistically Significant ($p < 0.05$)" if res['w_pval_r20'] < 0.05 else "Not Statistically Significant ($p \\ge 0.05$)"

        md.extend([
            f"### 2.{list(paired_stats_results.keys()).index(comp_name)+1} {comp_name}",
            "",
            f"- **Mean Difference in MRR (Target - Base)**: **{res['mean_delta_mrr']:+.4f}**",
            f"  - **95% Clustered Bootstrap CI**: `[{res['ci_mrr'][0]:+.4f}, {res['ci_mrr'][1]:+.4f}]`",
            f"  - **Wilcoxon Signed-Rank Test**: $p = {res['w_pval_mrr']:.4f}$ ({sig_mrr})",
            f"  - **Paired $t$-test**: $t = {res['t_stat_mrr']:.3f}$, $p = {res['t_pval_mrr']:.4f}$",
            f"  - **Query-Level Outcome**: **{res['wins_mrr']} Wins, {res['ties_mrr']} Ties, {res['losses_mrr']} Losses**",
            "",
            f"- **Mean Difference in Recall@20 (Target - Base)**: **{res['mean_delta_r20']:+.4f}**",
            f"  - **95% Clustered Bootstrap CI**: `[{res['ci_r20'][0]:+.4f}, {res['ci_r20'][1]:+.4f}]`",
            f"  - **Wilcoxon Signed-Rank Test**: $p = {res['w_pval_r20']:.4f}$ ({sig_r20})",
            f"  - **Paired $t$-test**: $t = {res['t_stat_r20']:.3f}$, $p = {res['t_pval_r20']:.4f}$",
            f"  - **Query-Level Outcome**: **{res['wins_r20']} Wins, {res['ties_r20']} Ties, {res['losses_r20']} Losses**",
            "",
            f"- **Mean Difference in Token Yield (BCY@8k)**: **{res['mean_delta_bcy']:+.4f}**",
            f"  - **95% Clustered Bootstrap CI**: `[{res['ci_bcy'][0]:+.4f}, {res['ci_bcy'][1]:+.4f}]`",
            f"  - **Query-Level Outcome**: **{res['wins_bcy']} Wins, {res['ties_bcy']} Ties, {res['losses_bcy']} Losses**",
            "",
        ])

    md.extend([
        "---",
        "",
        "## 3. PER-TASK BREAKDOWN",
        "",
        "| Task Type | Sample Count | System ID | MRR | Recall@20 | BCY@8k |",
        "| :--- | :---: | :--- | :---: | :---: | :---: |",
    ])

    for t in tasks:
        for s in systems:
            tb = task_breakdown[t][s]
            md.append(f"| `{t}` | {tb['count']} | `{s}` | {tb['mrr']:.4f} | {tb['r20']:.4f} | {tb['bcy']:.4f} |")

    md.extend([
        "",
        "---",
        "",
        "## 4. PER-LANGUAGE BREAKDOWN",
        "",
        "| Language | Query Count | System ID | MRR | Recall@20 | BCY@8k |",
        "| :--- | :---: | :--- | :---: | :---: | :---: |",
    ])

    for l in languages:
        for s in systems:
            lb = lang_breakdown[l][s]
            md.append(f"| `{l}` | {lb['count']} | `{s}` | {lb['mrr']:.4f} | {lb['r20']:.4f} | {lb['bcy']:.4f} |")

    out_md = ROOT_DIR / "research" / "stage3_6" / "PAIRED_STATISTICS.md"
    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"\nWrote PAIRED_STATISTICS.md to {out_md}")


if __name__ == "__main__":
    run_paired_statistics()
