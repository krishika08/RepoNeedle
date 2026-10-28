# REPONEEDLE STAGE 3.9: REPRODUCTION GUIDE

This guide provides instructions to reproduce the Stage 3.9 controlled ablation matrix, ranking failure diagnosis, statistical significance calculations, and runtime profiling.

---

## 1. PRE-FLIGHT ENVIRONMENT & WORKSPACE CHECK

Verify the repository state:
```bash
git checkout research-program
git rev-parse HEAD
# Expected base: fcab83b (or latest Stage 3.9 commit)
```

Ensure Python dependencies are installed:
```bash
python -m pip install -e .
python -m pip install numpy scipy networkx pytest
```

---

## 2. REPRODUCING THE DIAGNOSTIC HYPOTHESIS TESTING

To run the root-cause diagnostic script across all 345 queries:
```bash
python research/stage3_9/diagnose_ranking_failures.py
```
This tests Hypotheses A through E and demonstrates that disabling query-independent PageRank raises MRR from 0.1399 to 0.2033.

---

## 3. REPRODUCING THE FULL ABLATION MATRIX (11 CONFIGURATIONS)

To evaluate all 11 configurations across all 345 queries and 218 repository snapshots:
```bash
python research/stage3_9/run_ablation_matrix.py
```
Outputs generated:
- `research/stage3_9/ABLATION_RESULTS.csv` (summary table with official token-budgeted BCY@8k)
- `research/stage3_9/CANONICAL_PER_QUERY_RESULTS.csv` (3,795 rows: 345 queries $\times$ 11 configurations)
- `research/stage3_9/PER_REPOSITORY_RESULTS.csv` (per-repo breakdown across 25 repos)

---

## 4. REPRODUCING STATISTICAL SIGNIFICANCE & TRAIN/TEST SPLIT

To run paired bootstrap resampling ($B=10,000$, seed=42), Wilcoxon signed-rank tests, and the 15-dev / 10-test repository cross-validation:
```bash
python research/stage3_9/compute_statistics.py
```
Output generated:
- `research/stage3_9/STATISTICAL_ANALYSIS.md`

---

## 5. REPRODUCING RUNTIME & MEMORY PROFILING

To profile indexing time, query latency percentiles (p50, p90, p95, p99), and process RSS via Windows PSAPI:
```bash
python research/stage3_9/audit_runtime_and_memory.py
```
Output generated:
- `research/stage3_9/RUNTIME_MEMORY_RESULTS.csv`

---

## 6. RUNNING THE UNIT & REGRESSION TEST SUITE

Run all 71 tests in the repository:
```bash
python -m pytest tests/ -v
```
All 71 tests, including `tests/test_stage3_9_recovery.py`, must pass.
