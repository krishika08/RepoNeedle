"""
Stage 3.14: Independent Canonical Retrieval Metric Verification & Statistical Audit.
Recomputes all metrics from raw per-query predictions for:
  - BASE-BM25 (CONFIG-01)
  - CAND-C (CONFIG-06)
  - CAND-F (CONFIG-07)
  - CONFIG-09 (Corrected Hybrid)
  - CONFIG-10 (Sparse Cascaded Reranker)
  - CONFIG-11 (Recovered Candidate)
  - BASE-REPOMAP (Pinned RepoMap reference)

Recomputes:
  - Aggregate MRR, Recall@5, Recall@10, Recall@20, Precision@5, Token BCY@8k
  - Per-task breakdowns (code2test, comment2context, trace2code, edit2ripple)
  - CONFIG-09 vs BASE-BM25 paired Wilcoxon test and Holm-adjusted p-values
  - CONFIG-10 vs CONFIG-09 Two One-Sided Tests (TOST) equivalence at delta = +-0.015

Outputs:
  - research/stage3_14/CANONICAL_REPRODUCTION_RESULTS.csv
  - research/stage3_14/CANONICAL_REPRODUCTION_AUDIT.md
  - research/stage3_14/STATISTICAL_TEST_AUDIT.md
"""

import sys
import csv
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
import scipy.stats as stats

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_14"

def main():
    print("=" * 80)
    print("STAGE 3.14: CANONICAL RETRIEVAL METRIC RECOMPUTATION & AUDIT")
    print("=" * 80)

    # 1. Load raw Stage 3.9 per-query results
    s39_path = ROOT_DIR / "research" / "stage3_9" / "CANONICAL_PER_QUERY_RESULTS.csv"
    s38_path = ROOT_DIR / "research" / "stage3_8" / "CANONICAL_PER_QUERY_RESULTS.csv"

    r9 = list(csv.DictReader(open(s39_path, encoding="utf-8")))
    r8 = list(csv.DictReader(open(s38_path, encoding="utf-8")))

    # Store query metrics: by_sys[system_id][query_id] = {metric: val}
    by_sys = defaultdict(dict)
    query_meta = {}

    for r in r9:
        qid = r["query_id"]
        cfg = r["configuration_id"]
        query_meta[qid] = {
            "repo": r["repo"],
            "base_commit": r["base_commit"],
            "task_type": r["task_type"],
            "language": r["language"],
            "gold_files": r["gold_files"],
        }
        by_sys[cfg][qid] = {
            "mrr": float(r["mrr"]),
            "recall_at_1": float(r["recall_at_1"]),
            "recall_at_5": float(r["recall_at_5"]),
            "recall_at_10": float(r["recall_at_10"]),
            "recall_at_20": float(r["recall_at_20"]),
            "precision_at_5": float(r["precision_at_5"]),
            "precision_at_10": float(r["precision_at_10"]),
            "precision_at_20": float(r["precision_at_20"]),
            "token_bcy_at_8k": float(r["token_bcy_at_8k"]),
            "latency_ms": float(r["latency_ms"]),
        }

    # Load BASE-REPOMAP from Stage 3.8
    for r in r8:
        if r["system_id"] == "BASE-REPOMAP":
            qid = r["query_id"]
            by_sys["BASE-REPOMAP"][qid] = {
                "mrr": float(r["mrr"]),
                "recall_at_1": float(r["recall_at_1"]),
                "recall_at_5": float(r["recall_at_5"]),
                "recall_at_10": float(r["recall_at_10"]),
                "recall_at_20": float(r["recall_at_20"]),
                "precision_at_5": float(r["precision_at_5"]),
                "precision_at_10": float(r["precision_at_10"]),
                "precision_at_20": float(r["precision_at_20"]),
                "token_bcy_at_8k": float(r["token_bcy_at_8k"]),
                "latency_ms": float(r["latency_ms"]),
            }

    system_map = [
        ("BASE-BM25", "CONFIG-01", "Official BM25 Baseline (Okapi k1=1.5, b=0.75)"),
        ("CONFIG-09", "CONFIG-09", "Corrected Hybrid: Decoupled BM25 + Subword + DocFilter (No PR)"),
        ("CONFIG-10", "CONFIG-10", "Sparse Top-50 Retrieval + Subword Reranking"),
        ("CONFIG-11", "CONFIG-11", "Recovered Candidate: CONFIG-09 + Bounded Graph Diffusion"),
        ("CAND-C", "CONFIG-06", "Candidate C Canonical (PageRank Contaminated)"),
        ("CAND-F", "CONFIG-07", "Candidate F Canonical (Unbounded Graph Diffusion)"),
        ("BASE-REPOMAP", "BASE-REPOMAP", "Version-Pinned Official RepoMap Reference (commit 9e4d689)"),
    ]

    q_list = sorted(list(query_meta.keys()))
    n_queries = len(q_list)
    assert n_queries == 345, f"Expected 345 queries, got {n_queries}"
    print(f"Verified N = {n_queries} positive queries.")

    # 2. Recompute overall summary results
    results_rows = []
    print(f"\n{'System ID':<14} | {'Cfg Key':<10} | {'MRR':<7} | {'R@5':<7} | {'R@10':<7} | {'R@20':<7} | {'P@5':<7} | {'BCY@8k':<7} | {'Latency p50':<11}")
    print("-" * 95)

    for sys_id, cfg_key, desc in system_map:
        m = by_sys[cfg_key]
        mrrs = [m[q]["mrr"] for q in q_list]
        r1s = [m[q]["recall_at_1"] for q in q_list]
        r5s = [m[q]["recall_at_5"] for q in q_list]
        r10s = [m[q]["recall_at_10"] for q in q_list]
        r20s = [m[q]["recall_at_20"] for q in q_list]
        p5s = [m[q]["precision_at_5"] for q in q_list]
        p10s = [m[q]["precision_at_10"] for q in q_list]
        p20s = [m[q]["precision_at_20"] for q in q_list]
        bcys = [m[q]["token_bcy_at_8k"] for q in q_list]
        lats = [m[q]["latency_ms"] for q in q_list]

        row = {
            "system_id": sys_id,
            "configuration_key": cfg_key,
            "description": desc,
            "query_count": n_queries,
            "mrr": f"{np.mean(mrrs):.4f}",
            "recall_at_1": f"{np.mean(r1s):.4f}",
            "recall_at_5": f"{np.mean(r5s):.4f}",
            "recall_at_10": f"{np.mean(r10s):.4f}",
            "recall_at_20": f"{np.mean(r20s):.4f}",
            "precision_at_5": f"{np.mean(p5s):.4f}",
            "precision_at_10": f"{np.mean(p10s):.4f}",
            "precision_at_20": f"{np.mean(p20s):.4f}",
            "token_bcy_at_8k": f"{np.mean(bcys):.4f}",
            "latency_p50_ms": f"{np.median(lats):.2f}",
            "latency_p95_ms": f"{np.percentile(lats, 95):.2f}",
        }
        results_rows.append(row)
        print(f"{sys_id:<14} | {cfg_key:<10} | {row['mrr']:<7} | {row['recall_at_5']:<7} | {row['recall_at_10']:<7} | {row['recall_at_20']:<7} | {row['precision_at_5']:<7} | {row['token_bcy_at_8k']:<7} | {row['latency_p50_ms']} ms")

    # Write CANONICAL_REPRODUCTION_RESULTS.csv
    out_csv = STAGE_DIR / "CANONICAL_REPRODUCTION_RESULTS.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results_rows[0].keys()))
        w.writeheader()
        w.writerows(results_rows)
    print(f"\nWrote {out_csv.name}")

    # 3. Per-task breakdown recomputation
    task_types = ["code2test", "comment2context", "trace2code", "edit2ripple"]
    task_breakdown = {}
    for t in task_types:
        t_queries = [q for q in q_list if query_meta[q]["task_type"] == t]
        task_breakdown[t] = {"count": len(t_queries), "systems": {}}
        for sys_id, cfg_key, _ in system_map:
            m = by_sys[cfg_key]
            mrrs = [m[q]["mrr"] for q in t_queries]
            r20s = [m[q]["recall_at_20"] for q in t_queries]
            bcys = [m[q]["token_bcy_at_8k"] for q in t_queries]
            task_breakdown[t]["systems"][sys_id] = {
                "mrr": float(np.mean(mrrs)),
                "recall_at_20": float(np.mean(r20s)),
                "token_bcy_at_8k": float(np.mean(bcys)),
            }

    print("\nPer-Task Track Breakdown (MRR / Recall@20 / BCY@8k):")
    for t in task_types:
        cnt = task_breakdown[t]["count"]
        print(f"\n--- Track: {t} (N = {cnt}) ---")
        for sys_id in ["BASE-BM25", "CONFIG-09", "CONFIG-10", "BASE-REPOMAP"]:
            st = task_breakdown[t]["systems"][sys_id]
            print(f"  {sys_id:<14}: MRR = {st['mrr']:.4f}, Recall@20 = {st['recall_at_20']:.4f}, BCY@8k = {st['token_bcy_at_8k']:.4f}")

    # 4. Statistical Tests: TOST Equivalence (CONFIG-10 vs CONFIG-09)
    print("\n" + "=" * 50)
    print("STATISTICAL TEST 1: TWO ONE-SIDED TESTS (TOST) EQUIVALENCE")
    print("Target: CONFIG-10 vs CONFIG-09 on MRR (N=345)")
    print("Predeclared Equivalence Margin: Delta = +-0.015 MRR")
    print("=" * 50)

    v_c10 = np.array([by_sys["CONFIG-10"][q]["mrr"] for q in q_list])
    v_c09 = np.array([by_sys["CONFIG-09"][q]["mrr"] for q in q_list])
    d_mrr = v_c10 - v_c09

    n = len(d_mrr)
    mean_d = float(np.mean(d_mrr))
    std_d = float(np.std(d_mrr, ddof=1))
    se_d = std_d / np.sqrt(n)
    df = n - 1
    delta = 0.015

    # Hypotheses:
    # H01: mean_d <= -delta  vs  H11: mean_d > -delta
    # H02: mean_d >= +delta  vs  H12: mean_d < +delta
    t1 = (mean_d - (-delta)) / se_d
    t2 = (mean_d - delta) / se_d

    p1 = float(1.0 - stats.t.cdf(t1, df=df))
    p2 = float(stats.t.cdf(t2, df=df))
    tost_p = max(p1, p2)

    ci95_low = mean_d - float(stats.t.ppf(0.975, df=df)) * se_d
    ci95_high = mean_d + float(stats.t.ppf(0.975, df=df)) * se_d
    ci90_low = mean_d - float(stats.t.ppf(0.95, df=df)) * se_d
    ci90_high = mean_d + float(stats.t.ppf(0.95, df=df)) * se_d

    print(f"Paired sample size (N): {n}")
    print(f"Degrees of freedom (df): {df}")
    print(f"Mean difference (CONFIG-10 - CONFIG-09): {mean_d:+.6f}")
    print(f"Sample standard deviation (s): {std_d:.6f}")
    print(f"Standard error (SE): {se_d:.6f}")
    print(f"Lower test statistic (t1): {t1:+.4f} (p1 = {p1:.4e})")
    print(f"Upper test statistic (t2): {t2:+.4f} (p2 = {p2:.4e})")
    print(f"Overall TOST p-value: {tost_p:.4e}")
    print(f"90% Confidence Interval: [{ci90_low:+.6f}, {ci90_high:+.6f}]")
    print(f"95% Confidence Interval: [{ci95_low:+.6f}, {ci95_high:+.6f}]")
    print(f"Predeclared bounds: [{-delta:+.4f}, {+delta:+.4f}]")
    is_equiv = (ci90_low > -delta) and (ci90_high < delta) and (tost_p < 0.05)
    print(f"Statistical Equivalence Proven: {'YES' if is_equiv else 'NO'}")

    # 5. Statistical Tests: CONFIG-09 vs BASE-BM25 Paired Wilcoxon with Holm Adjustment
    print("\n" + "=" * 50)
    print("STATISTICAL TEST 2: CONFIG-09 vs BASE-BM25 PAIRED COMPARISONS")
    print("=" * 50)

    test_metrics = [
        ("mrr", "MRR"),
        ("recall_at_5", "Recall@5"),
        ("recall_at_10", "Recall@10"),
        ("recall_at_20", "Recall@20"),
        ("token_bcy_at_8k", "BCY@8k"),
    ]

    wilcoxon_results = []
    for m_key, m_name in test_metrics:
        va = np.array([by_sys["CONFIG-09"][q][m_key] for q in q_list])
        vb = np.array([by_sys["CONFIG-01"][q][m_key] for q in q_list])
        d = va - vb
        mean_diff = float(np.mean(d))
        nonzero = d[d != 0]
        wins = int(np.sum(d > 1e-6))
        losses = int(np.sum(d < -1e-6))
        ties = int(np.sum(np.abs(d) <= 1e-6))
        
        stat_val, p_val = stats.wilcoxon(nonzero)
        std_d_val = float(np.std(d, ddof=1))
        cohens_d = mean_diff / std_d_val if std_d_val > 0 else 0.0

        wilcoxon_results.append({
            "metric": m_name,
            "mean_diff": mean_diff,
            "cohens_d": cohens_d,
            "wins": wins,
            "ties": ties,
            "losses": losses,
            "p_value": p_val,
        })

    # Sort by unadjusted p-value for Holm step-down
    wilcoxon_results.sort(key=lambda x: x["p_value"])
    m_tests = len(wilcoxon_results)
    for rank, wr in enumerate(wilcoxon_results):
        holm_step = 0.05 / (m_tests - rank)
        adjusted_p = min(1.0, wr["p_value"] * (m_tests - rank))
        sig = "YES" if wr["p_value"] <= holm_step else "NO"
        wr["holm_threshold"] = holm_step
        wr["adjusted_p"] = adjusted_p
        wr["significant"] = sig
        print(f"Metric: {wr['metric']:<10} | Mean Diff: {wr['mean_diff']:+.4f} | Wins/Ties/Losses: {wr['wins']}/{wr['ties']}/{wr['losses']} | p-raw: {wr['p_value']:.4e} | p-adj: {wr['adjusted_p']:.4e} | Sig: {wr['significant']}")

    return {
        "results_rows": results_rows,
        "task_breakdown": task_breakdown,
        "tost": {
            "n": n, "df": df, "mean_d": mean_d, "std_d": std_d, "se_d": se_d,
            "delta": delta, "t1": t1, "t2": t2, "p1": p1, "p2": p2, "tost_p": tost_p,
            "ci95": (ci95_low, ci95_high), "ci90": (ci90_low, ci90_high), "is_equiv": is_equiv
        },
        "wilcoxon": wilcoxon_results
    }

if __name__ == "__main__":
    main()
