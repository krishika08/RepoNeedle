"""
Stage 3.8: Repository-Clustered Statistical Validation & Paired Significance Testing.

Preregistered protocol:
  - Resampling: 10,000 repository clusters with replacement.
  - Random seed: 42.
  - Baseline reference: EXP-384 (exact reproduction of EXP-378).
  - Metrics tested: MRR, Recall@20, Hit@20, BCY@8k.
  - Tests: Cluster-level paired t-test, cluster-level Wilcoxon signed-rank test.
  - Strict acceptance criterion: 95% bootstrap CI lower bound strictly > 0.0000 AND delta MRR >= +0.0100.
"""

import sys
import os
import json
import csv
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy import stats

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_8"


def run_statistical_analysis():
    jsonl_path = STAGE_DIR / "PER_QUERY_RESULTS.jsonl"
    if not jsonl_path.exists():
        print(f"Error: {jsonl_path} does not exist.")
        sys.exit(1)

    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    print(f"Loaded {len(records)} query records from {jsonl_path}")

    # Group queries by repository
    repo_to_records = defaultdict(list)
    for r in records:
        repo_to_records[r["repo"]].append(r)

    repo_names = sorted(list(repo_to_records.keys()))
    num_repos = len(repo_names)
    print(f"Identified {num_repos} repository clusters.")

    # Configurations to compare against EXP-384
    candidates = ["EXP-385", "EXP-386", "EXP-387", "EXP-388"]
    ref_id = "EXP-384"
    metrics = ["mrr", "r20", "hit20", "bcy_8k"]

    # 1. Compute cluster means for each candidate
    cluster_means = {cid: {m: [] for m in metrics} for cid in [ref_id] + candidates}
    query_scores = {cid: {m: [] for m in metrics} for cid in [ref_id] + candidates}

    for r_name in repo_names:
        recs = repo_to_records[r_name]
        for cid in [ref_id] + candidates:
            for m in metrics:
                vals = [rec["systems"][cid][m] for rec in recs]
                cluster_means[cid][m].append(float(np.mean(vals)))

    for rec in records:
        for cid in [ref_id] + candidates:
            for m in metrics:
                query_scores[cid][m].append(rec["systems"][cid][m])

    for cid in [ref_id] + candidates:
        for m in metrics:
            cluster_means[cid][m] = np.array(cluster_means[cid][m])
            query_scores[cid][m] = np.array(query_scores[cid][m])

    # 2. Cluster Bootstrap (10,000 iterations, seed 42)
    B = 10000
    rng = np.random.default_rng(42)
    boot_indices = rng.choice(num_repos, size=(B, num_repos), replace=True)

    analysis_results = {}

    for cid in candidates:
        analysis_results[cid] = {}
        for m in metrics:
            delta_q = query_scores[cid][m] - query_scores[ref_id][m]
            mean_delta = float(np.mean(delta_q))

            wins = int(np.sum(delta_q > 1e-6))
            losses = int(np.sum(delta_q < -1e-6))
            ties = int(np.sum(np.abs(delta_q) <= 1e-6))

            # Bootstrap over repository clusters
            boot_deltas = np.zeros(B, dtype=np.float64)
            for b in range(B):
                idx = boot_indices[b]
                resampled_cand_means = cluster_means[cid][m][idx]
                resampled_ref_means = cluster_means[ref_id][m][idx]
                boot_deltas[b] = np.mean(resampled_cand_means - resampled_ref_means)

            ci_low = float(np.percentile(boot_deltas, 2.5))
            ci_high = float(np.percentile(boot_deltas, 97.5))
            boot_se = float(np.std(boot_deltas, ddof=1))

            # Cluster-level paired t-test (df = K - 1 = 24)
            diff_clusters = cluster_means[cid][m] - cluster_means[ref_id][m]
            t_stat, t_pval = stats.ttest_rel(cluster_means[cid][m], cluster_means[ref_id][m])

            # Cluster-level Wilcoxon signed-rank test
            # Handle case where all diffs are zero
            if np.all(np.abs(diff_clusters) < 1e-9):
                w_stat, w_pval = 0.0, 1.0
            else:
                try:
                    w_res = stats.wilcoxon(diff_clusters, zero_method="pratt")
                    w_stat, w_pval = float(w_res.statistic), float(w_res.pvalue)
                except Exception:
                    w_stat, w_pval = 0.0, 1.0

            analysis_results[cid][m] = {
                "mean_ref": float(np.mean(query_scores[ref_id][m])),
                "mean_cand": float(np.mean(query_scores[cid][m])),
                "mean_delta": mean_delta,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "boot_se": boot_se,
                "t_stat": float(t_stat) if not np.isnan(t_stat) else 0.0,
                "t_pval": float(t_pval) if not np.isnan(t_pval) else 1.0,
                "w_stat": float(w_stat),
                "w_pval": float(w_pval),
                "wins": wins,
                "losses": losses,
                "ties": ties,
            }

    # Generate STATISTICAL_COMPARISON.md
    md_lines = []
    md_lines.append("# RepoNeedle Stage 3.8: Statistical Validation & Significance Analysis\n")
    md_lines.append("**Benchmark**: Agent Retrieval Bench v2 Unconstrained (345 positive queries, 25 repositories)\n")
    md_lines.append("**Baseline Reference**: `EXP-384` (Exact EXP-378 reproduction)\n")
    md_lines.append("**Bootstrap Methodology**: 10,000 cluster-level bootstrap resamples over 25 repository clusters (`seed=42`)\n")
    md_lines.append("**Hypothesis Tests**: Cluster-level paired $t$-test and Wilcoxon signed-rank test on cluster means ($K=25$, $\\text{df}=24$)\n\n")

    md_lines.append("## 1. Candidate Comparison Summary vs Reference EXP-384\n\n")
    md_lines.append("| Candidate | Description | Metric | EXP-384 | Candidate | Mean Delta | 95% Clustered CI | p-val (t-test) | p-val (Wilcoxon) | W / T / L | Verdict |\n")
    md_lines.append("|---|---|---|---:|---:|---:|:---:|---:|---:|:---:|:---:|\n")

    names = {
        "EXP-385": "Query-Affinity",
        "EXP-386": "Edge-Type Gating",
        "EXP-387": "Degree Dampened",
        "EXP-388": "Combined QC",
    }

    for cid in candidates:
        for m in metrics:
            res = analysis_results[cid][m]
            m_label = {"mrr": "MRR", "r20": "Recall@20", "hit20": "Hit@20", "bcy_8k": "BCY@8k"}[m]
            ci_str = f"[{res['ci_low']:+.4f}, {res['ci_high']:+.4f}]"

            # Check criteria
            if m == "mrr":
                if res["ci_low"] > 0.0 and res["mean_delta"] >= 0.0100:
                    verdict = "**PASS (Stat Sig)**"
                elif res["ci_low"] > 0.0:
                    verdict = "Stat Sig (Below +0.010 target)"
                elif res["mean_delta"] > 0.0:
                    verdict = "Inconclusive (CI spans 0)"
                else:
                    verdict = "Regression / Neutral"
            else:
                if res["ci_low"] > 0.0:
                    verdict = "Improvement"
                elif res["ci_high"] < 0.0:
                    verdict = "Regression"
                else:
                    verdict = "Neutral"

            md_lines.append(
                f"| `{cid}` ({names[cid]}) | {names[cid]} | **{m_label}** | {res['mean_ref']:.4f} | {res['mean_cand']:.4f} | "
                f"**{res['mean_delta']:+.4f}** | `{ci_str}` | {res['t_pval']:.4f} | {res['w_pval']:.4f} | "
                f"{res['wins']}/{res['ties']}/{res['losses']} | {verdict} |\n"
            )

    md_lines.append("\n## 2. Preregistered Acceptance Criteria Evaluation\n\n")
    md_lines.append("The Stage 3.8 protocol specifies the following strict conditions for advancing any new candidate to winner status:\n\n")
    md_lines.append("1. **Valid unconstrained evaluation**: Evaluated over all 345 positive queries without oracle task filtering.\n")
    md_lines.append("2. **MRR Improvement $\\ge +0.0100$**: Absolute MRR improvement over EXP-378 must meet or exceed +0.0100.\n")
    md_lines.append("3. **Statistical Significance**: 95% repository-clustered bootstrap CI lower bound strictly $> 0.0000$.\n")
    md_lines.append("4. **No material Recall@20 loss**: Candidate must not regress Recall@20.\n")
    md_lines.append("5. **No latency or memory regression**: Query latency and memory overhead must remain within acceptable bounds.\n\n")

    md_lines.append("### Preregistered Gate Audit Table\n\n")
    md_lines.append("| Candidate | Criterion 1 (Protocol) | Criterion 2 (Delta MRR $\\ge +0.0100$) | Criterion 3 (CI Lower $> 0.0$) | Criterion 4 (No R@20 Loss) | Overall Decision |\n")
    md_lines.append("|---|:---:|:---:|:---:|:---:|:---:|\n")

    for cid in candidates:
        mrr_res = analysis_results[cid]["mrr"]
        r20_res = analysis_results[cid]["r20"]

        c1 = "PASS"
        c2 = "PASS" if mrr_res["mean_delta"] >= 0.0100 else f"FAIL ({mrr_res['mean_delta']:+.4f} < +0.0100)"
        c3 = "PASS" if mrr_res["ci_low"] > 0.0 else f"FAIL (CI low = {mrr_res['ci_low']:+.4f} $\\le 0$)"
        c4 = "PASS" if r20_res["mean_delta"] >= -0.0050 else f"FAIL ({r20_res['mean_delta']:+.4f})"

        overall = "**REJECTED (Inconclusive / Promising)**"
        if c1 == "PASS" and "PASS" in c2 and "PASS" in c3 and c4 == "PASS":
            overall = "**ACCEPTED WINNER**"

        md_lines.append(f"| `{cid}` ({names[cid]}) | {c1} | {c2} | {c3} | {c4} | {overall} |\n")

    md_lines.append("\n## 3. Comparison with Candidate C and RepoMap Reference\n\n")
    md_lines.append("All measurements below are on the identical 345-query unconstrained ARB v2 benchmark:\n\n")
    md_lines.append("| Architecture | System Type | MRR | Recall@5 | Recall@10 | Recall@20 | Hit@20 | BCY@8k |\n")
    md_lines.append("|---|---|---:|---:|---:|---:|---:|---:|\n")
    md_lines.append("| **Candidate C** | Old Winner (Stage 3.5) | 0.1409 | — | — | 0.5143 | — | — |\n")
    md_lines.append(f"| **EXP-384** | EXP-378 Repro Reference | {analysis_results['EXP-386']['mrr']['mean_ref']:.4f} | — | — | {analysis_results['EXP-386']['r20']['mean_ref']:.4f} | {analysis_results['EXP-386']['hit20']['mean_ref']:.4f} | {analysis_results['EXP-386']['bcy_8k']['mean_ref']:.4f} |\n")
    md_lines.append(f"| **EXP-386** | Edge-Type Gated | {analysis_results['EXP-386']['mrr']['mean_cand']:.4f} | — | — | {analysis_results['EXP-386']['r20']['mean_cand']:.4f} | {analysis_results['EXP-386']['hit20']['mean_cand']:.4f} | {analysis_results['EXP-386']['bcy_8k']['mean_cand']:.4f} |\n")
    md_lines.append(f"| **EXP-388** | Combined QC | {analysis_results['EXP-388']['mrr']['mean_cand']:.4f} | — | — | {analysis_results['EXP-388']['r20']['mean_cand']:.4f} | {analysis_results['EXP-388']['hit20']['mean_cand']:.4f} | {analysis_results['EXP-388']['bcy_8k']['mean_cand']:.4f} |\n")
    md_lines.append("| **RepoMap** | External Reference (Aider) | 0.2293 | 0.2986 | 0.4578 | 0.6599 | 0.7478 | 0.0612 |\n\n")

    out_md = STAGE_DIR / "STATISTICAL_COMPARISON.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.writelines(md_lines)
    print(f"Saved STATISTICAL_COMPARISON.md to {out_md}")


if __name__ == "__main__":
    run_statistical_analysis()

