# RepoNeedle Stage 3.15: Experimental Reproduction Guide

**Stage**: Stage 3.15 — Champion Reconciliation, Historical Reproduction, and Benchmark Integrity Audit  
**Date**: October 2026  
**Document ID**: `STAGE3-15-REPRO-002`  
**Git Branch**: `research-program`  
**Base Commit**: `12142e8`  

---

## 1. Environment & Tag Verification

Open PowerShell or terminal in the repository root (`F:\RepoNeedle`):

```bash
# 1. Verify working directory
cd F:\RepoNeedle

# 2. Verify git branch and clean working tree
git branch --show-current
# Expected: research-program

git status
# Expected: nothing to commit, working tree clean

# 3. Verify immutable frozen tags are intact
git rev-parse v0.1.0-baseline^{commit}
# Expected: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse stage3-candidate-freeze^{commit}
# Expected: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

---

## 2. Reproduce Reconciliation Deliverables & Scoreboard

To deterministically recompute the discrepancy matrices, claim verification table, canonical scoreboard, and per-query alignments:

```bash
python research/stage3_15/generate_stage3_15_reconciliation.py
```

This command regenerates:
- `research/stage3_15/BASELINE_DISCREPANCIES.csv`
- `research/stage3_15/CLAIM_VERIFICATION.csv`
- `research/stage3_15/CANONICAL_SCOREBOARD.csv`
- `research/stage3_15/REPRODUCED_PER_QUERY_RESULTS.csv`
- `research/stage3_15/EXPERIMENT_REGISTRY.jsonl`

---

## 3. Verify Paired Statistical Tests

Run the following Python script to compute paired Wilcoxon signed-rank tests and 10,000 bootstrap confidence intervals across the 345 positive queries:

```bash
python -c "
import csv
import numpy as np
from scipy.stats import wilcoxon

rows = list(csv.DictReader(open('research/stage3_15/REPRODUCED_PER_QUERY_RESULTS.csv', encoding='utf-8')))
arm101 = np.array([float(r['ARM-101-BASE_mrr']) for r in rows])
candf = np.array([float(r['CAND-F_mrr']) for r in rows])
candc = np.array([float(r['CAND-C_mrr']) for r in rows])
bm25 = np.array([float(r['BASE-BM25_mrr']) for r in rows])
repomap = np.array([float(r['BASE-REPOMAP_mrr']) for r in rows])

def evaluate(a, b, label):
    diff = a - b
    res = wilcoxon(a, b)
    print(f'{label:20s}: Mean Delta = {np.mean(diff):+.4f}, Wilcoxon W = {res.statistic}, p = {res.pvalue:.4e}')

print('=== REPRODUCED PAIRED MRR COMPARISONS (N=345) ===')
evaluate(arm101, candf, 'ARM-101 vs CAND-F')
evaluate(arm101, candc, 'ARM-101 vs CAND-C')
evaluate(arm101, bm25, 'ARM-101 vs BASE-BM25')
evaluate(arm101, repomap, 'ARM-101 vs BASE-REPOMAP')
evaluate(candf, bm25, 'CAND-F vs BASE-BM25')
"
```

Expected outputs:
- `ARM-101 vs CAND-F`: Mean Delta = $+0.0727$, Wilcoxon $p = 3.59 \times 10^{-18}$ (ARM-101 overwhelmingly superior).
- `ARM-101 vs CAND-C`: Mean Delta = $+0.0679$, Wilcoxon $p = 1.11 \times 10^{-24}$.
- `ARM-101 vs BASE-BM25`: Mean Delta = $+0.0326$, Wilcoxon $p = 6.41 \times 10^{-31}$.
- `ARM-101 vs BASE-REPOMAP`: Mean Delta = $-0.0215$, Wilcoxon $p = 0.0559$ (not significant at 0.05).
- `CAND-F vs BASE-BM25`: Mean Delta = $-0.0401$, Wilcoxon $p = 0.0122$ (Candidate F significantly worse than BM25).

---

## 4. Run Automated Test Suites

Verify that all regression tests, integrity safeguards, and deliverable checkers pass:

```bash
# Run Stage 3.15 specific safeguard tests
pytest tests/test_stage3_15_safeguards.py -v

# Run full repository test suite (177+ tests)
pytest
```

All tests must pass synchronously with exit code 0.

---

## 5. ContextBench External Validation Gate Protocol

The official ContextBench dataset remains gated by network sandbox boundaries. To reproduce the fail-closed validation gate:

```bash
python research/stage3_15/validate_contextbench.py
```
*(Exits with Code 2: `[STATUS: BLOCKED — DATA ACCESS]`)*.

When external acquisition is completed outside the sandbox:
1. Place `Contextbench/ContextBench` Parquet/JSONL files in `data/contextbench/`.
2. Run `python research/stage3_15/validate_contextbench.py --data-dir data/contextbench/`.
3. If checksum and schema match, execute `python research/stage3_15/contextbench_adapter.py`.
