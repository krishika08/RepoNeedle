# RepoNeedle Stage 3.10.2: Reproduction Instructions

This guide provides exact commands to independently reproduce the Stage 3.10.2 canonical evaluation integrity audit, runtime/memory benchmarks, statistical validation, and test suite.

## 1. Environment & Setup

Ensure the workspace is on branch `research-program` and required dependencies are installed:

```powershell
git checkout research-program
pip install pytest scipy numpy
```

## 2. Verify Frozen Tags

Confirm that both immutable tags remain unchanged:

```powershell
git rev-parse "v0.1.0-baseline^{commit}"
# Output must be: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse "stage3-candidate-freeze^{commit}"
# Output must be: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

## 3. Run the Stage 3.10.2 Integrity Test Suite

Execute the hand-checkable independent metric verification and artifact integrity unit tests:

```powershell
pytest tests/test_stage3_10_2_integrity.py -v
```

All 5 tests must pass:
1. `test_stage3_10_2_artifacts_exist`
2. `test_independent_metric_implementations`
3. `test_recomputed_metrics_match_canonical`
4. `test_statistical_claim_reproducibility`
5. `test_runtime_memory_audit`

## 4. Run the Full Repository Test Suite

Execute the full repository test suite (150 tests):

```powershell
pytest
```

## 5. Re-run Independent Canonical Metric Recomputation & Statistical Audit

To re-execute the ground-up metric recomputation across all 345 positive ARB v2 queries and re-run the 10,000-replicate bootstrap statistical validation:

```powershell
python research/stage3_10_2/run_canonical_audit.py
```

This updates:
- `research/stage3_10_2/INDEPENDENT_METRIC_RECOMPUTATION.csv`
- `research/stage3_10_2/PER_QUERY_PAIRED_DIFFERENCES.csv`
- `research/stage3_10_2/PER_TASK_RESULTS.csv`
- `research/stage3_10_2/PER_REPOSITORY_RESULTS.csv`
- `research/stage3_10_2/REPRODUCTION_MATRIX.csv`
- `research/stage3_10_2/statistical_summary.json`

## 6. Re-run Performance and Memory Scaling Audit

To re-run cold index construction, warm query latency (25 trials), and process RSS / peak working set profiling for Click and Caddy:

```powershell
python research/stage3_10_2/audit_performance.py
```

This updates:
- `research/stage3_10_2/RUNTIME_MEMORY_RESULTS.csv`
