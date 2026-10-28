"""
Comprehensive Baseline Reconciliation & Statistical Validation.
Compares Stage 1 Baseline (reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl)
with Stage 2 Anchor Configurations (EXP-001, EXP-002, EXP-004, EXP-016)
using 10,000 repository-clustered bootstrap resamples and paired tests.
"""

import json
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy import stats

ROOT_DIR = Path(__file__).resolve().parent.parent

# 1. Load Stage 1 records
stage1_recs = {}
for line in open(ROOT_DIR / "reports" / "full_arb_validation" / "PER_SAMPLE_RESULTS.jsonl", encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        stage1_recs[r["sample_id"]] = r

# 2. Load Stage 2 records
stage2_recs = {}
for line in open(ROOT_DIR / "research" / "stage2_results" / "PER_SAMPLE_ABLATIONS.jsonl", encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        stage2_recs[r["sample_id"]] = r

common_ids = [sid for sid in stage1_recs if sid in stage2_recs]
print(f"Loaded {len(common_ids)} common samples for paired reconciliation.")

# Group by repo for clustered bootstrap
repo_samples = defaultdict(list)
for sid in common_ids:
    repo = stage1_recs[sid]["repo"]
    repo_samples[repo].append(sid)
unique_repos = list(repo_samples.keys())
print(f"Grouped across {len(unique_repos)} repository clusters.")

def clustered_bootstrap_diff(metric_fn_1, metric_fn_2, n_bootstrap=10000, seed=42):
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_bootstrap):
        sampled_repos = rng.choice(unique_repos, size=len(unique_repos), replace=True)
        sampled_sids = []
        for r in sampled_repos:
            sampled_sids.extend(repo_samples[r])
        v1 = np.mean([metric_fn_1(sid) for sid in sampled_sids])
        v2 = np.mean([metric_fn_2(sid) for sid in sampled_sids])
        diffs.append(v1 - v2)
    diffs = np.array(diffs)
    mean_d = float(np.mean(diffs))
    ci_low = float(np.percentile(diffs, 2.5))
    ci_high = float(np.percentile(diffs, 97.5))
    return mean_d, ci_low, ci_high

comparisons = [
    ("EXP-001 (S2 Full w/ Skel) vs Stage 1 Baseline",
     lambda sid: stage2_recs[sid]["evaluations"]["EXP-001"]["mrr"],
     lambda sid: stage1_recs[sid]["reponeedle"]["mrr"]),
    ("EXP-002 (S2 Full Full-Only) vs Stage 1 Baseline",
     lambda sid: stage2_recs[sid]["evaluations"]["EXP-002"]["mrr"],
     lambda sid: stage1_recs[sid]["reponeedle"]["mrr"]),
    ("EXP-004 (S2 Static Hybrid) vs Stage 1 Baseline",
     lambda sid: stage2_recs[sid]["evaluations"]["EXP-004"]["mrr"],
     lambda sid: stage1_recs[sid]["reponeedle"]["mrr"]),
    ("EXP-004 (S2 Static Hybrid) vs EXP-016 (S2 BM25)",
     lambda sid: stage2_recs[sid]["evaluations"]["EXP-004"]["mrr"],
     lambda sid: stage2_recs[sid]["evaluations"]["EXP-016"]["mrr"]),
    ("EXP-003 (S2 Static w/ Skel) vs EXP-004 (S2 Static Full) on BCY@8k",
     lambda sid: stage2_recs[sid]["evaluations"]["EXP-003"]["bcy@8k"],
     lambda sid: stage2_recs[sid]["evaluations"]["EXP-004"]["bcy@8k"]),
]

print("\n" + "=" * 90)
print("PAIRED STATISTICAL RECONCILIATION (10,000 CLUSTERED BOOTSTRAP RESAMPLES)")
print("=" * 90)

for name, fn1, fn2 in comparisons:
    v1_all = [fn1(sid) for sid in common_ids]
    v2_all = [fn2(sid) for sid in common_ids]
    d_raw = np.array(v1_all) - np.array(v2_all)

    mean_d, ci_low, ci_high = clustered_bootstrap_diff(fn1, fn2)
    t_stat, p_val = stats.ttest_rel(v1_all, v2_all)
    try:
        w_stat, w_pval = stats.wilcoxon(v1_all, v2_all)
    except Exception:
        w_stat, w_pval = 0.0, 1.0

    wins = sum(1 for d in d_raw if d > 1e-6)
    losses = sum(1 for d in d_raw if d < -1e-6)
    ties = sum(1 for d in d_raw if abs(d) <= 1e-6)

    print(f"\nComparison: {name}")
    print(f"  Mean Difference:     {mean_d:+.4f} (95% Clustered CI: [{ci_low:+.4f}, {ci_high:+.4f}])")
    print(f"  Paired t-test:       t = {t_stat:.3f}, p = {p_val:.6e}")
    print(f"  Wilcoxon test:       W = {w_stat:.1f}, p = {w_pval:.6e}")
    print(f"  Wins / Ties / Losses: {wins} / {ties} / {losses}")
    sig_str = "YES (p < 0.05)" if ci_low > 0 or ci_high < 0 else "NO (Crosses zero)"
    print(f"  Significant:         {sig_str}")

