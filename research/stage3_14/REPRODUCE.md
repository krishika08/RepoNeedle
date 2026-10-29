# RepoNeedle Stage 3.14 — Reproduction Guide

This document provides exact, deterministic instructions for reproducing the Stage 3.14 Language-Aware Hub Attenuation experiments and statistical tests.

---

## 1. Environment & Prerequisites

- **Python Version**: 3.12+ (tested on Python 3.12.10 x64 on Windows)
- **Git Branch**: `research-program`
- **Dependencies**:
  ```bash
  pip install -e .
  pip install pytest scipy numpy
  ```

---

## 2. Verify Repository State & Immutable Tags

Confirm the repository integrity before running experiments:

```bash
# Verify current branch and commit
git status
git rev-parse HEAD

# Verify immutable baseline tags (must match exactly)
git rev-parse v0.1.0-baseline^{commit}
# Expected: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse stage3-candidate-freeze^{commit}
# Expected: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

---

## 3. Run the Full Stage 3.14 Benchmark Pipeline

To execute the full 9-system evaluation across all 345 positive ARB v2 queries and 218 snapshots:

```bash
python research/stage3_14/run_stage3_14_experiments.py
```

This script:
1. Loads the 345 positive ARB v2 queries from `benchmarks/arb_v2/queries_positive.jsonl`.
2. Evaluates the 9 systems:
   - `BASE-BM25`
   - `CONTROL-CASCADE`
   - `ARM-101-BASE`
   - `ARM-111-UNIFORM`
   - `LANG-CALIBRATED`
   - `STRUCTURAL-ROLE`
   - `COMBINED-LANG-ROLE`
   - `DEGREE-THRESHOLD-15`
   - `BASE-REPOMAP`
3. Outputs:
   - `research/stage3_14/PER_QUERY_RESULTS.csv` (345 query rows)
   - `research/stage3_14/PER_LANGUAGE_RESULTS.csv` (stratified by Go, Python, Rust, TS, Java)
   - `research/stage3_14/PER_REPOSITORY_RESULTS.csv` (stratified across 25 repositories)
   - `research/stage3_14/STATISTICAL_ANALYSIS.json` (5-fold repository CV, 10,000 bootstrap CIs, paired Wilcoxon signed-rank tests with Holm-Bonferroni correction)
   - `research/stage3_14/RUNTIME_AND_MEMORY.csv` (latency and isolated process RSS)
   - `research/stage3_14/EXPERIMENT_REGISTRY.jsonl` (EXP-050 through EXP-058)

---

## 4. Verify Benchmark Results Interactively

Run the following Python snippet to verify the metrics from the generated artifacts:

```python
import csv, json

with open("research/stage3_14/STATISTICAL_ANALYSIS.json") as f:
    stats = json.load(f)

print("Paired comparisons vs ARM-101-BASE:")
for sys_id, comp in stats["comparisons_vs_arm101_base"].items():
    print(f"  {sys_id:20s}: Delta MRR = {comp['mean_delta_mrr']:+.5f} "
          f"(95% CI: [{comp['ci_95_lower']:+.5f}, {comp['ci_95_upper']:+.5f}], "
          f"Holm p = {comp['holm_adjusted_p_value']:.4f})")

# Verify overall MRRs from query results
with open("research/stage3_14/PER_QUERY_RESULTS.csv") as f:
    reader = csv.DictReader(f)
    systems = [k.replace("_reciprocal_rank", "") for k in reader.fieldnames if k.endswith("_reciprocal_rank")]
    mrr_sums = {s: 0.0 for s in systems}
    count = 0
    for row in reader:
        count += 1
        for s in systems:
            mrr_sums[s] += float(row[f"{s}_reciprocal_rank"])

print(f"\nRecomputed MRR across {count} queries:")
for s in sorted(systems):
    print(f"  {s:20s}: {mrr_sums[s] / count:.4f}")
```

Expected output:
- `ARM-101-BASE`: `0.2078`
- `ARM-111-UNIFORM`: `0.2061`
- `LANG-CALIBRATED`: `0.2073`
- `STRUCTURAL-ROLE`: `0.2078`
- `COMBINED-LANG-ROLE`: `0.2073`
- `DEGREE-THRESHOLD-15`: `0.2078`
- `CONTROL-CASCADE`: `0.1897`
- `BASE-BM25`: `0.1752`
- `BASE-REPOMAP`: `0.2293`

---

## 5. Execute Automated Test Suite

Run pytest to verify all regression and safeguard checks:

```bash
pytest
```

All tests must pass synchronously.
