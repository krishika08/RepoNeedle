# RepoNeedle Stage 3.11: Exact Reproduction Guide

This guide allows an independent auditor to reproduce all Stage 3.11 function-level call graph research artifacts, benchmarks, statistical analyses, and test suites.

---

## 1. Environment & Setup

Ensure the workspace is on branch `research-program` and required dependencies are installed:

```powershell
git checkout research-program
pip install pytest scipy numpy networkx
```

---

## 2. Verify Immutable Frozen Tags

Confirm that both immutable tags remain unchanged:

```powershell
git rev-parse "v0.1.0-baseline^{commit}"
# Expected output: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse "stage3-candidate-freeze^{commit}"
# Expected output: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

---

## 3. Run Stage 3.11 Unit and Integrity Test Suites

Execute both the function graph unit tests and the historical audit test suite:

```powershell
pytest tests/test_stage3_11_function_graph.py -v
pytest tests/test_stage3_11_integrity.py -v
```

All tests must pass deterministically.

---

## 4. Run the Full Repository Test Suite

Execute the entire repository regression test suite (158 tests):

```powershell
pytest
```

---

## 5. Re-Run Function-Level Graph Retrieval Benchmark Pipeline

To independently re-execute full index construction, function graph building, and evaluation across all 345 positive ARB v2 queries and 82 abstention queries over 271 snapshots:

```powershell
python research/stage3_11/run_stage3_11_evaluation.py
```

This updates:
- `research/stage3_11/RETRIEVAL_RESULTS.csv` (345 query rows)
- `research/stage3_11/GRAPH_COVERAGE_RESULTS.csv` (271 snapshot rows)
- `research/stage3_11/PER_TASK_RESULTS.csv` (4 task rows)
- `research/stage3_11/PER_REPOSITORY_RESULTS.csv` (25 repository rows)
- `research/stage3_11/CONTEXT_PACKING_RESULTS.csv` (5 system rows)
- `research/stage3_11/RUNTIME_AND_MEMORY.csv` (5 system rows)
- `research/stage3_11/statistical_summary.json` (10,000-replicate bootstrap CIs, Wilcoxon test, Holm adjustments)
- `research/stage3_11/EXPERIMENT_REGISTRY.jsonl`

---

## 6. Legacy Cross-Stage Audit Reproduction

To re-run the legacy Stage 3.11 cross-stage reconciliation audit:

```powershell
python research/stage3_11/run_stage3_11_audit.py
```
