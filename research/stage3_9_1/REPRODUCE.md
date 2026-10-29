# REPONEEDLE STAGE 3.9.1: INDEPENDENT REPRODUCTION GUIDE

This guide provides deterministic instructions to independently reproduce the Stage 3.9.1 metric reconciliation, full-coverage 2,415-row recomputation dataset, invariant audits, and statistical tests.

---

## 1. PRE-FLIGHT ENVIRONMENT & WORKSPACE CHECK

Verify the repository state:
```bash
git checkout research-program
git rev-parse HEAD
# Expected base: 064e619d1bb2bf707fd356435ec9dd2831cde571
```

Confirm that frozen baseline and candidate tags remain untouched:
```bash
git rev-parse "v0.1.0-baseline^{commit}"
# Must output: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse "stage3-candidate-freeze^{commit}"
# Must output: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

Ensure Python dependencies are installed:
```bash
python -m pip install -e .
python -m pip install numpy scipy networkx pytest
```

---

## 2. REPRODUCING THE INDEPENDENT 2,415-ROW RECOMPUTATION

To independently recompute all 7 configurations across all 345 queries with full tall-row coverage ($345 \times 7 = 2,415$ rows):
```bash
python research/stage3_9_1/generate_stage3_9_1_audit.py
```

Outputs generated in `research/stage3_9_1/`:
- `CANONICAL_METRICS.csv`: Single authoritative summary table computed directly from raw rows.
- `INDEPENDENT_RECOMPUTATION.csv`: Full tall-format 2,415-row per-query per-configuration dataset.
- `RUN_PROVENANCE.json`: Checksums, environment metadata, and execution parameters.

---

## 3. REPRODUCING THE TOP-3 PRESERVATION INVARIANT AUDIT

Run the focused test suite protecting the cascaded ranking invariants:
```bash
pytest tests/test_stage3_9_cascade.py -v
```

Run the complete regression suite across all components:
```bash
pytest tests/
# Expected: 126 passed
```

---

## 4. REPRODUCING STATISTICAL VERIFICATION

To verify the repository-clustered bootstrap ($B = 10,000$, seed = 42) and paired Wilcoxon signed-rank tests:
```bash
python -c "
import csv
from collections import defaultdict
import numpy as np
import scipy.stats as stats

s39_path = 'research/stage3_9/PER_QUERY_CASCADE_RESULTS.csv'
rows = list(csv.DictReader(open(s39_path, encoding='utf-8')))
repo_to_queries = defaultdict(list)
for r in rows:
    repo_to_queries[r['repo']].append(r)
repos = sorted(list(repo_to_queries.keys()))
K = len(repos)

def clustered_bootstrap(target_col, base_col, B=10000, seed=42):
    rng = np.random.default_rng(seed)
    repo_diff_sums, repo_counts = [], []
    for repo in repos:
        q_list = repo_to_queries[repo]
        diffs = [float(q[target_col]) - float(q[base_col]) for q in q_list]
        repo_diff_sums.append(sum(diffs))
        repo_counts.append(len(diffs))
    repo_diff_sums, repo_counts = np.array(repo_diff_sums), np.array(repo_counts)
    boot_means = []
    for _ in range(B):
        idx = rng.choice(K, size=K, replace=True)
        boot_means.append(np.sum(repo_diff_sums[idx]) / np.sum(repo_counts[idx]))
    boot_means = np.array(boot_means)
    return boot_means, np.percentile(boot_means, 2.5), np.percentile(boot_means, 97.5)

_, ci_l_bm, ci_h_bm = clustered_bootstrap('cascade_mrr', 'bm25_mrr')
diff_bm = [float(r['cascade_mrr']) - float(r['bm25_mrr']) for r in rows]
w_bm = stats.wilcoxon([float(r['cascade_mrr']) for r in rows], [float(r['bm25_mrr']) for r in rows], zero_method='pratt')

print(f'Cascade vs BM25: mean={np.mean(diff_bm):+.4f}, 95% Clustered CI=[{ci_l_bm:+.4f}, {ci_h_bm:+.4f}], p={w_bm.pvalue:.4e}')
"
```
Expected output:
`Cascade vs BM25: mean=+0.0131, 95% Clustered CI=[+0.0106, +0.0156], p=1.1919e-37`

