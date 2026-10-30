# RepoNeedle Stage 3.18 — Deterministic Reproduction Guide

This document provides exact, copy-pasteable instructions for independently reproducing all Stage 3.18 candidate provenance audits, metric reconciliations, and cluster-aware statistical tests.

---

## 1. Verify Git State & Baseline Tags

From the repository root (`F:\RepoNeedle`):

```powershell
# 1. Verify current branch
git branch --show-current
# Expected: research-program

# 2. Verify immutable baseline tags
git rev-parse 'v0.1.0-baseline^{commit}'
# Expected: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse 'stage3-candidate-freeze^{commit}'
# Expected: cd7f3b01e28695f9a9357e0815069e0eae85baca

# 3. Verify clean working tree and zero diffs on production code
git status
git diff HEAD -- reponeedle/
# Expected: clean, zero diffs
```

---

## 2. Generate Candidate Leaderboard & Query-Level Results

Execute the deterministic artifact generator to produce `CANDIDATE_LEADERBOARD.csv`, `CANDIDATE_QUERY_LEVEL_RESULTS.csv`, and `METRIC_RECONCILIATION.csv`:

```powershell
python research/stage3_18/generate_stage3_18_artifacts.py
```

**Expected Console Output**:
```
Wrote 345 query rows to F:\RepoNeedle\research\stage3_18\CANDIDATE_QUERY_LEVEL_RESULTS.csv
Wrote 5 leaderboard rows to F:\RepoNeedle\research\stage3_18\CANDIDATE_LEADERBOARD.csv
Wrote 10 reconciliation rows to F:\RepoNeedle\research\stage3_18\METRIC_RECONCILIATION.csv
Wrote 7 experiment entries to F:\RepoNeedle\research\stage3_18\EXPERIMENT_REGISTRY.jsonl
```

---

## 3. Verify SHA-256 Hashes of Core Artifacts

Verify that generated artifacts match their recorded cryptographic hashes:

```powershell
python -c "
import hashlib
from pathlib import Path

files = [
    'research/stage3_18/CANDIDATE_QUERY_LEVEL_RESULTS.csv',
    'research/stage3_18/CANDIDATE_LEADERBOARD.csv',
    'research/stage3_18/METRIC_RECONCILIATION.csv',
    'research/stage3_18/EXPERIMENT_REGISTRY.jsonl'
]
for f in files:
    h = hashlib.sha256(Path(f).read_bytes()).hexdigest()
    print(f'{f}: {h}')
"
```

---

## 4. Recompute Paired Statistical Tests & 10,000-Replicate Cluster Bootstrap

Execute the repository-cluster-aware bootstrap analysis:

```powershell
python -c "
import csv
import numpy as np
from collections import defaultdict
from scipy.stats import wilcoxon

with open('research/stage3_18/CANDIDATE_QUERY_LEVEL_RESULTS.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

repo_queries = defaultdict(list)
for i, r in enumerate(rows):
    repo_queries[r['repository']].append(i)

repo_names = list(repo_queries.keys())
n_repos = len(repo_names)
repo_idx_lists = [np.array(repo_queries[r]) for r in repo_names]

systems = ['BASE-BM25', 'BASE-REPOMAP', 'CAND-C', 'ARM-101-BASE', 'CAND-F']
mrr_data = {s: np.array([float(r[f'{s}_mrr']) for r in rows]) for s in systems}

np.random.seed(42)
n_reps = 10000
sampled_repos_idx = np.random.randint(0, n_repos, size=(n_reps, n_repos))

pairs = [
    ('ARM-101-BASE', 'BASE-BM25'),
    ('ARM-101-BASE', 'CAND-F'),
    ('ARM-101-BASE', 'BASE-REPOMAP'),
    ('CAND-F', 'BASE-BM25')
]

for s1, s2 in pairs:
    deltas = []
    for b in range(n_reps):
        chosen_repo_indices = sampled_repos_idx[b]
        query_indices = np.concatenate([repo_idx_lists[k] for k in chosen_repo_indices])
        d = mrr_data[s1][query_indices].mean() - mrr_data[s2][query_indices].mean()
        deltas.append(d)
    d_arr = np.array(deltas)
    ci_low, ci_high = np.percentile(d_arr, [2.5, 97.5])
    p_boot = 2.0 * min((d_arr <= 0).mean(), (d_arr >= 0).mean())
    w_res = wilcoxon(mrr_data[s1], mrr_data[s2], alternative='two-sided')
    print(f'{s1} vs {s2}:')
    print(f'  Delta MRR: {d_arr.mean():+.4f}')
    print(f'  95% Clustered CI: [{ci_low:+.4f}, {ci_high:+.4f}]')
    print(f'  Cluster Bootstrap p: {p_boot:.6f}')
    print(f'  Query-level Wilcoxon p: {w_res.pvalue:.6e}')
"
```

---

## 5. Run Automated Safeguard & Integrity Tests

Run pytest to verify all Stage 3.18 safeguards and integrity contracts:

```powershell
pytest tests/test_stage3_18_candidate_provenance_and_reconciliation.py -v
```

All tests must pass synchronously.
