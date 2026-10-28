# Stage 3.8: Complete Reproduction Guide

**Document ID**: `STAGE3-8-REPRO-001`  
**Stage**: Stage 3.8 — Reproducibility Lock, Metric Reconciliation, and Evidence Audit  
**Date**: October 28, 2026  
**Status**: Step-by-Step Verifiable Reproduction Guide  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  

---

## 1. Environment Verification

Ensure Python environment meets requirements. From repository root `F:\RepoNeedle`, execute:

```powershell
python -c "import sys, numpy, scipy, pytest; print('Python:', sys.version.split()[0], '| NumPy:', numpy.__version__, '| SciPy:', scipy.__version__, '| Pytest:', pytest.__version__)"
```
- Expected Python: `>= 3.12`
- Expected Packages: `numpy >= 1.26`, `scipy >= 1.13`, `pytest >= 8.0`

Verify that the frozen Git tags have not moved:
```powershell
git rev-parse "v0.1.0-baseline^{commit}" "stage3-candidate-freeze^{commit}"
```
Expected output:
```
8e0042553a14b6e3c6cf5b35823c4da84181a8e9
cd7f3b01e28695f9a9357e0815069e0eae85baca
```

---

## 2. Automated Regression Unit Tests

Execute the Stage 3.8 unit test suite covering hand-calculated fixtures, dataset alignment, and reconciled point estimates:

```powershell
python -m pytest tests/test_stage3_8_reproducibility.py -v
```
- Expected output: `8 passed in ~0.3s`

Execute the full RepoNeedle test suite across all subsystems:
```powershell
python -m pytest tests/
```
- Expected output: `67 passed` (50 base + 9 Stage 3.7 + 8 Stage 3.8).

---

## 3. Re-Generating Canonical Predictions

To re-generate `research/stage3_8/CANONICAL_PER_QUERY_RESULTS.csv` from source predictions and compute canonical token-budgeted BCY:

```powershell
python research/stage3_8/build_canonical_results.py
```
- Expected output:
  `[DONE] Wrote 1380 canonical records to F:\RepoNeedle\research\stage3_8\CANONICAL_PER_QUERY_RESULTS.csv in ~35s.`

---

## 4. Re-Running the Statistical Audit & Clustered Bootstrap

To recompute paired differences, 95% repository-clustered bootstrap intervals ($B=10,000$, seed=42), and Wilcoxon signed-rank tests:

```powershell
python -c "
import csv, numpy as np, scipy.stats as stats
from collections import defaultdict

with open('research/stage3_8/CANONICAL_PER_QUERY_RESULTS.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

by_sys = defaultdict(dict)
all_queries = set()
repo_by_query = {}
for r in rows:
    qid = r['query_id']
    sid = r['system_id']
    all_queries.add(qid)
    repo_by_query[qid] = r['repo']
    by_sys[sid][qid] = {'r20': float(r['recall_at_20']), 'mrr': float(r['mrr'])}

q_list = sorted(list(all_queries))
repo_clusters = defaultdict(list)
for idx, q in enumerate(q_list):
    repo_clusters[repo_by_query[q]].append(idx)

unique_repos = list(repo_clusters.keys())
n_repos = len(unique_repos)
rng = np.random.default_rng(42)
B = 10000

diff_r20 = np.array([by_sys['CAND-F'][q]['r20'] - by_sys['BASE-BM25'][q]['r20'] for q in q_list])
boot_r20 = [np.mean(diff_r20[[i for r in rng.choice(unique_repos, size=n_repos, replace=True) for i in repo_clusters[r]]]) for _ in range(B)]

print('R@20 Point Delta:', round(np.mean(diff_r20), 4))
print('R@20 95% Clustered CI: [', round(np.percentile(boot_r20, 2.5), 4), ',', round(np.percentile(boot_r20, 97.5), 4), ']')
"
```
Expected output:
```
R@20 Point Delta: 0.0529
R@20 95% Clustered CI: [ -0.0091 , 0.1689 ]
```

---

## 5. Artifact Hash Verification

Verify SHA-256 hashes for all Stage 3.8 artifacts:

```powershell
python -c "
import hashlib
from pathlib import Path
for p in sorted(list(Path('research/stage3_8').glob('*.csv')) + list(Path('research/stage3_8').glob('*.md'))):
    c = p.read_bytes()
    print(f'{p.name:<35} | {len(c.splitlines()):<5} lines | {hashlib.sha256(c).hexdigest()}')
"
```
