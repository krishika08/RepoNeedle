# Phase 6 Audit Report: Certified Reproducibility Guide & Benchmark Harness

**Document ID**: `V1_1-AUDIT-REPRO-001`  
**Date**: November 2, 2026  
**Auditor**: Principal Information Retrieval Researcher & Benchmark Architect  
**Status**: OFFICIALLY CERTIFIED & REPRODUCIBLE  

---

## 1. Single Reproducible Benchmark Command

To reproduce all reported Phase R6 metrics, candidate rankings, per-repository breakdowns, and runtime latencies from raw data in a single command, execute:

```bash
python research/v1_accuracy/ranking_0_80/v1_1_audit/run_reproducible_benchmark.py
```

### Execution Output:
- Parses the compressed benchmark dataset [`independent_benchmark.json.gz`](file:///F:/RepoNeedle/research/v1_accuracy/ranking_0_80/r6/independent_benchmark.json.gz).
- Validates SHA-256 data integrity.
- Evaluates 180 tasks across 18 unseen open-source repositories.
- Ranks candidate files under Baseline Treatment B and Champion Treatment D.
- Prints the exact partition summary, per-repository breakdown, and latency statistics.
- Emits certified raw per-query ranks to [`reproducible_benchmark_run.json`](file:///F:/RepoNeedle/research/v1_accuracy/ranking_0_80/v1_1_audit/reproducible_benchmark_run.json).

---

## 2. Pinned Environmental & Provenance Signatures

| Parameter | Pinned Value / Cryptographic Signature | Verification Method |
| :--- | :--- | :--- |
| **Git Commit Reference** | `8e55dc736b818213d2f1ca184fa323512c5b7eb8` | `git rev-parse HEAD` |
| **Benchmark Dataset File** | `research/v1_accuracy/ranking_0_80/r6/independent_benchmark.json.gz` | Relative path |
| **Dataset File SHA-256** | `e4b0dad8a7a98bc07c08410f17338671902dd5d048adda97b9acd7d56d5212bd` | `hashlib.sha256` |
| **Target Architecture** | Python $\ge 3.10$ (Certified on 3.10.11 and 3.12.10) | Standard CPython |
| **Dependencies** | `numpy>=1.24.0`, `scipy>=1.10.0`, `networkx>=3.0` | `pip install .` |

---

## 3. Pinned Production Parameter Specification

All hyperparameters governing Champion Treatment D are statically pinned in [`production_champion_config.json`](file:///F:/RepoNeedle/research/v1_accuracy/ranking_0_80/v1_1_audit/production_champion_config.json):

```json
{
  "enable_graph": true,
  "fallback_on_error": true,
  "impact_multiplier": 3.0,
  "sfs_multiplier": 0.01,
  "tip_multiplier_non_test": 0.85,
  "tip_multiplier_test": 1.45,
  "weight_confirmed_build": 0.4,
  "weight_confirmed_call": 0.8,
  "weight_confirmed_import": 0.75,
  "weight_confirmed_symbol": 0.8,
  "weight_heuristic_ancestor": 0.3,
  "weight_heuristic_dir_proximity": 0.75,
  "weight_heuristic_doc": 0.35,
  "weight_heuristic_test_stem": 0.85
}
```

---

## 4. Authoritative Metric Tolerances

When executed on any compatible platform, the output metrics must match the following reference table within floating-point tolerance ($\epsilon < 0.0001$):

| Partition | Queries | Baseline Treatment B MRR | Champion Treatment D MRR | Expected Delta ($\Delta \text{MRR}$) |
| :--- | :---: | :---: | :---: | :---: |
| **Train** | 90 | **0.6213** | **0.6546** | **+0.0333** |
| **Validation** | 40 | **0.6472** | **0.6708** | **+0.0236** |
| **Held-Out** | 50 | **0.5215** | **0.5467** | **+0.0252** |
| **Pooled Cohort** | 180 | **0.5994** | **0.6282** | **+0.0288** |

### Per-Repository Regression Bound:
- Regressions across all 18 repositories: **0** (All repositories exhibit $\Delta \text{MRR} \ge 0.0000$).

