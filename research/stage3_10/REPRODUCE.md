# RepoNeedle Stage 3.10 — Reproduction Guide

This document describes how to independently reproduce the Stage 3.10 Class-to-Test Invocation Graph research results and verify all invariants.

## 1. Prerequisites & Environment

- Windows OS (or Linux / macOS with compatible Python 3.12+ environment)
- Python 3.12+
- Pytest and dependencies installed:
  ```bash
  pip install pytest scipy numpy
  ```

## 2. Verify Frozen Tags and Starting State

Verify that the frozen reference tags remain untouched before running any evaluations:

```bash
git checkout research-program
git rev-parse v0.1.0-baseline
# Expected: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse stage3-candidate-freeze
# Expected: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

## 3. Run Targeted Class-to-Test Unit Tests

Execute the 10 targeted Stage 3.10 unit tests verifying AST parsing, evidence priority, generic symbol suppression, and rank-preservation invariants:

```bash
pytest tests/test_stage3_10_class_to_test.py -v
```

Execute the full regression test suite (143 tests):

```bash
pytest
```

## 4. Run the Full 345-Query ARB v2 Canonical Evaluation

To reproduce the four evaluation arms (`CONTROL-CASCADE`, `TEST-GRAPH`, `DEGREE-CONTROL`, `GRAPH-ABLATION`) across all 218 snapshots and 345 queries:

```bash
python research/stage3_10/evaluate_stage3_10.py
```

This will generate:
- `research/stage3_10/PER_QUERY_RESULTS.csv` (all 345 queries with per-arm metrics)
- `research/stage3_10/PER_TASK_RESULTS.csv` (task-stratified breakdown)
- `research/stage3_10/PER_REPOSITORY_RESULTS.csv` (repository-stratified breakdown)
- `research/stage3_10/GRAPH_EDGE_DIAGNOSTICS.csv` (graph structure, edge counts, unresolved references)
- `research/stage3_10/stage3_10_evaluation_summary.json` (aggregate metrics, bootstrap intervals, Wilcoxon test)

## 5. Verify Invariants and Integrity

Run the verification test suite:

```bash
pytest tests/test_stage3_10_verification.py -v
```

All assertions must pass cleanly.
