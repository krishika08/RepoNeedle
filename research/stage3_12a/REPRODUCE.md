# RepoNeedle Stage 3.12A: Exact Reproduction Guide

This guide allows an independent auditor to reproduce all Stage 3.12A reconciliation artifacts, verified raw per-query data, and statistical analyses.

---

## 1. Environment & Setup

Ensure the workspace is on branch `research-program` and required dependencies are installed:

```powershell
git checkout research-program
pip install pytest scipy numpy
```

---

## 2. Verify Immutable Frozen Tags

Confirm that both immutable tags remain unchanged:

```powershell
git rev-parse "v0.1.0-baseline^{commit}"
# Expected: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse "stage3-candidate-freeze^{commit}"
# Expected: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

---

## 3. Run Stage 3.12A Reconciliation Test Suite

Execute the hand-checkable reconciliation test suite:

```powershell
pytest tests/test_stage3_12a_reconciliation.py -v
```

All tests must pass deterministically.

---

## 4. Run the Full Repository Test Suite

Execute the entire repository regression test suite (164 tests):

```powershell
pytest
```

---

## 5. Re-Run the Canonical Reconciliation Pipeline

To independently re-execute query alignment, raw per-query merging, and the 10,000-replicate repository-clustered bootstrap:

```powershell
python research/stage3_12a/run_stage3_12a_reconciliation.py
```

This generates:
- `research/stage3_12a/CANONICAL_PER_QUERY_RESULTS.csv` (345 query rows)
- `research/stage3_12a/CANONICAL_METRIC_SUMMARY.csv` (7 system rows)
- `research/stage3_12a/statistical_reconciliation.json` (Clustered bootstrap CIs & Wilcoxon test results)
