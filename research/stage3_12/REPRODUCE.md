# RepoNeedle Stage 3.12 — Reproduction Guide

This guide describes how to reproduce all performance hardening benchmarks, canonical evaluations, memory audits, and the 2^3 factorial experiment on the `research-program` branch.

## Prerequisites

- Operating System: Windows 10/11 x64 (or Linux with appropriate sysconf for RSS)
- Python 3.10+
- Installed Dependencies: `numpy`, `scipy`, `pytest`, `psutil` (optional; Windows PSAPI used via ctypes)
- Repository: `F:\RepoNeedle`
- Frozen Tags: `v0.1.0-baseline` (`8e00425`), `stage3-candidate-freeze` (`cd7f3b0`)

---

## 1. Verify Repository Integrity & Frozen Tags

```powershell
# 1. Confirm current branch and clean working tree
git status

# 2. Verify frozen tags have not moved
git rev-parse v0.1.0-baseline
# Expected: 8e00425a1768822650059e6ea3565074cbca6117

git rev-parse stage3-candidate-freeze
# Expected: cd7f3b0fe16091217e92828b6d080c55490fd38c
```

---

## 2. Execute Automated Verification Tests

Verify the inverted index optimization, bitwise score parity, candidate slicing, and artifact schemas:

```powershell
python -m pytest tests/test_stage3_12_hardening.py -v
```

All tests should pass in under 5 seconds.

---

## 3. Run Stage 3.12 Fair Benchmarking Harness

To regenerate all CSV artifacts, runtime benchmarks, memory audits, and quality-speed trade-off curves:

```powershell
python research/stage3_12/run_stage3_12_benchmarks.py
```

Generated deliverables:
- `research/stage3_12/CANONICAL_REPRODUCTION.csv`
- `research/stage3_12/RUNTIME_BENCHMARKS.csv`
- `research/stage3_12/QUALITY_SPEED_TRADEOFF.csv`
- `research/stage3_12/MEMORY_BENCHMARKS.csv`
- `research/stage3_12/CLAIM_EVIDENCE_LEDGER.csv`
- `research/stage3_12/FAILURE_ANALYSIS.md`
- `research/stage3_12/EXPERIMENT_REGISTRY.jsonl`
- `research/stage3_12/STAGE3_12_REPORT.md`

---

## 4. Execute the 2^3 Factorial Experiment Pipeline

To execute the full 8-arm factorial benchmark across all 345 positive queries and 218 snapshots, computing all statistical tests (10,000 bootstrap replicates, Wilcoxon signed-rank tests, Holm-Bonferroni correction, ANOVA effects) and generating all canonical CSVs:

```powershell
python research/stage3_12/run_stage3_12_factorial.py
```

Generated factorial deliverables:
- `research/stage3_12/DESIGN_AND_PREREGISTRATION.md`
- `research/stage3_12/STAGE3_12_DECISION_REPORT.md`
- `research/stage3_12/CANONICAL_PER_QUERY_RESULTS.csv`
- `research/stage3_12/FACTORIAL_RESULTS.csv`
- `research/stage3_12/PER_TASK_RESULTS.csv`
- `research/stage3_12/REGRESSION_ANALYSIS.md`
- `research/stage3_12/STATISTICAL_ANALYSIS.json`
- `research/stage3_12/RUNTIME_AND_MEMORY.csv`
- `research/stage3_12/RUN_PROVENANCE.json`

---

## 5. Run Factorial Unit & Integrity Tests

Verify that all Stage 3.12 factorial deliverables exist, schemas match, and all preregistered constraints hold:

```powershell
python -m pytest tests/test_stage3_12_factorial.py -v
```

---

## 6. Run Full Regression Test Suite

Confirm that all existing and historical tests across RepoNeedle continue to pass:

```powershell
python -m pytest tests/
```
