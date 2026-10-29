# Reproducing RepoNeedle Stage 3.9.2 Deliverables

This guide provides exact, deterministic commands to reproduce the Stage 3.9.2 Cross-Stage Metric Reconciliation and Context-Budget Validity Audit.

---

## 1. Environment Verification

Confirm the Python environment, dependencies, and immutable frozen tags:

```bash
# Verify Python version (3.12.x required)
python --version

# Verify Git branch and commit
git status
git rev-parse HEAD

# Verify immutable baseline tags (must match recorded hashes)
git rev-parse "v0.1.0-baseline^{commit}"
# Expected: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse "stage3-candidate-freeze^{commit}"
# Expected: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

---

## 2. Execute Automated Regression & Budget Audit Tests

Run the full test suite, including the new deterministic budget audit tests:

```bash
# Run Stage 3.9.2 context budget and packing audit tests
pytest tests/test_stage3_9_2_budget_audit.py -v

# Run the complete test suite (133 tests)
pytest tests/
```

Expected output:
```
============================= 133 passed in 5.98s =============================
```

---

## 3. Regenerate Cross-Stage Reconciliation & Budget Artifacts

Execute the Stage 3.9.2 artifact generator:

```bash
python research/stage3_9_2/generate_stage3_9_2_artifacts.py
```

This command automatically regenerates:
1. `research/stage3_9_2/DISCREPANCY_MATRIX.csv`: Master ledger of historical discrepancies, root causes, deltas, and statuses.
2. `research/stage3_9_2/PER_QUERY_CROSS_STAGE_COMPARISON.csv`: Query-level (345 rows) comparison across Stage 2, 3.6, 3.9, and 3.9.1.
3. `research/stage3_9_2/PER_QUERY_BUDGET_COMPARISON.csv`: Query-level (345 rows) simulation of 5 context-budget policies.
4. `research/stage3_9_2/RUN_PROVENANCE.json`: Cryptographic SHA-256 hashes, environment metadata, and timestamps.

---

## 4. Inspecting Audit Deliverables

All documentation and evidence reports are located in `research/stage3_9_2/`:
- [`CROSS_STAGE_METRIC_AUDIT.md`](file:///F:/RepoNeedle/research/stage3_9_2/CROSS_STAGE_METRIC_AUDIT.md): Detailed root-cause investigation of Stage 3.5 vs Stage 3.9.1 score differences.
- [`HISTORICAL_REPRODUCTION.md`](file:///F:/RepoNeedle/research/stage3_9_2/HISTORICAL_REPRODUCTION.md): Step-by-step reproduction of historical workflows.
- [`BUDGET_METRIC_AUDIT.md`](file:///F:/RepoNeedle/research/stage3_9_2/BUDGET_METRIC_AUDIT.md): Unit analysis (char vs token) and packing policy simulation.
- [`STATISTICAL_AND_LATENCY_AUDIT.md`](file:///F:/RepoNeedle/research/stage3_9_2/STATISTICAL_AND_LATENCY_AUDIT.md): Bootstrap CIs, Wilcoxon tests, and latency profiling.
- [`CANONICAL_EVALUATION_CONTRACT.md`](file:///F:/RepoNeedle/research/stage3_9_2/CANONICAL_EVALUATION_CONTRACT.md): The binding evaluation contract for Stage 3.10+.
- [`STAGE3_9_2_DECISION.md`](file:///F:/RepoNeedle/research/stage3_9_2/STAGE3_9_2_DECISION.md): Formal gate decision and authorization.
