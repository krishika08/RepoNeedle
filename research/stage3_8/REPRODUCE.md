# RepoNeedle Stage 3.8: Complete Reproduction Guide

This document provides step-by-step instructions to reproduce the Stage 3.8 research findings, evaluation metrics, statistical significance tests, and runtime efficiency benchmarks.

---

## 1. Environment & Baseline Integrity Verification

Verify Python environment (Python 3.12+ on Windows) and ensure working directory is `F:\RepoNeedle`.

```powershell
# 1. Verify Git Branch and HEAD
git status
git rev-parse HEAD
# Expected starting commit: f61c6be926fa4df0caaba5a1bff5a0c2a00794d2

# 2. Verify Immutable Frozen Baseline Tags
git cat-file -p v0.1.0-baseline
# Expected target commit: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git cat-file -p stage3-candidate-freeze
# Expected target commit: cd7f3b01e28695f9a9357e0815069e0eae85baca

# 3. Verify Full Regression Test Suite
pytest
# Expected: 249 passed in ~8s
```

---

## 2. Execute Stage 3.8 Comprehensive Evaluation

Run the canonical unconstrained evaluation script across all 345 positive ARB v2 queries and 218 corpora:

```powershell
python research/stage3_8/scripts/evaluate_stage3_8_experiments.py
```

This generates:
- `research/stage3_8/PER_QUERY_RESULTS.jsonl`: Complete query-level predictions, metrics, and latency for all 5 systems.
- `research/stage3_8/RANKING_RESULTS.csv`: Canonical summary leaderboard across all positive ARB v2 samples.
- `research/stage3_8/EXPERIMENT_REGISTRY.jsonl`: Experiment registry records for EXP-384 through EXP-388.
- `research/stage3_8/REPOSITORY_LEVEL_RESULTS.csv`: Per-repository performance breakdown for all 25 evaluated repositories.

---

## 3. Execute Statistical Significance Testing

Run the 10,000-iteration repository-clustered bootstrap analysis with fixed seed 42:

```powershell
python research/stage3_8/scripts/compute_stage3_8_statistics.py
```

This generates:
- `research/stage3_8/STATISTICAL_COMPARISON.md`: Paired difference analysis, 95% bootstrap confidence intervals, paired $t$-test and Wilcoxon signed-rank tests, and acceptance gate audit.

---

## 4. Execute Isolated Runtime & Memory Profiling

Run the isolated efficiency benchmark across representative repositories:

```powershell
python research/stage3_8/scripts/benchmark_runtime_and_memory.py
```

This generates:
- `research/stage3_8/RUNTIME_AND_MEMORY.csv`: Index construction time, query latency (median, p95), retained index memory, and peak process RSS.

---

## 5. Verify Diagnostic Traces for Click and Clap

Run the forensic diagnosis script for `pallets/click` and `clap-rs/clap`:

```powershell
python research/stage3_8/scripts/diagnose_repository_regressions.py
```

This verifies `research/stage3_8/GRAPH_PROPAGATION_DIAGNOSTICS.csv`.
