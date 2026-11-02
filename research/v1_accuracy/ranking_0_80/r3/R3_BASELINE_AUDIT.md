# REPONEEDLE MISSION 0.80+ — PHASE R3
# DELIVERABLE 1: R3 BASELINE AUDIT & R2 RECONCILIATION REPORT

**Author**: Principal Information Retrieval Engineer, Search Relevance Architect  
**Date**: November 2, 2026  
**Status**: APPROVED & FROZEN  
**Target Milestone**: Phase R3 (AST Symbol Intelligence + BM25L Ranking)  

---

## 1. EXECUTIVE SUMMARY

Phase R3 of the RepoNeedle **Mission 0.80+ Ranking Intelligence Research Programme** builds upon the foundation established in Phase R2. Prior to introducing AST-level symbol matching and BM25 length-normalization variants, this audit rigorously verifies the working tree, test suite integrity, historical metric reproducibility, seed-trap reconciliation, classifier feature lineage, and statistical inference methodology.

### Key Audit Findings:
1. **Working Tree & Git State**: Clean working branch `v1.0-zero-failure`; frozen release tag `v0.1.0-release` intact.
2. **Test Suite Integrity**: Full suite passing bit-for-bit: **268 passed in 33.75s, 0 failures, 0 errors**.
3. **Metric Bit-for-Bit Reproduction**: Treatment A (Baseline M1), Treatment E (Champion: SFS + TIP), and Treatment H (Composite: SFS + TIP + SMS) reproduced exactly across all 345 queries, 25 repositories, and 3 repository-clustered splits.
4. **Seed-Trap Discrepancy Reconciliation**: The 48-query difference between R1 (259 traps) and R2 (211 traps) is fully accounted for: 47 queries stemmed from traceback/terminal log file references in `trace2code`, and 1 from incidental prose substring matching. Under strict, zero-oracle seed extraction, exactly 211 queries suffered from rank-1 seed traps, all 211 of which are eliminated by Treatment E.
5. **Zero Data Leakage & Feature Lineage**: `TestIntentClassifier` uses pure query-text lexical patterns; zero benchmark track labels, zero gold paths, and zero oracle features exist in the inference path.
6. **Repository-Clustered Statistical Inference**: Demonstrated that standard query-level bootstrap overstates confidence. Under repository-clustered bootstrap (10,000 resamples of repository clusters), Treatment E's 95% confidence interval on Validation is **`[+0.0170, +0.2195]`** (strictly positive, verifying true generalization).

---

## 2. REPOSITORY & GIT INTEGRITY AUDIT

### 2.1 Branch & Commit State
- **Active Git Branch**: `v1.0-zero-failure`
- **Tracking Branch**: `origin/v1.0-zero-failure` (Up to date)
- **Frozen Release Tag**: `v0.1.0-release` verified present and unmodified at commit `f599ee2289f07a7505ee461aa7b925f385c7ee0f`.
- **Historical Baselines**:
  - `reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl` (Official Frozen Baseline v0.1.0)
  - `research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz` (M1 Candidate Pool)
  - `research/v1_accuracy/ranking_0_80/r2/PER_QUERY_COMPARISON.jsonl` (Frozen R2 Benchmark Records)

### 2.2 Test Suite Execution
A complete test suite run was executed against the repository:
```bash
pytest tests/ -q
```
**Results**:
- **268 passed, 0 failures, 0 errors** in 33.75 seconds.
- Regression tests for CUD-Pack, ARM-101, Tokenizer, BM25 Index, Router, and R2 Ranker all pass without warnings or regressions.

---

## 3. R2 METRIC REPRODUCTION AUDIT

All 345 queries across 8 treatments in `research/v1_accuracy/ranking_0_80/r2/PER_QUERY_COMPARISON.jsonl` were re-evaluated using `research/v1_accuracy/ranking_0_80/r3/src/audit_r2_baseline.py`.

### 3.1 Split Distribution
- **Training Set**: 15 repositories, 210 queries
- **Validation Set**: 5 repositories, 60 queries
- **Held-Out Set**: 5 repositories, 75 queries
- **Total Universe**: 25 repositories, 345 queries

### 3.2 Authoritative Baseline Comparisons

| Metric | Split | Treatment A (M1 Baseline) | Treatment E (Champion: SFS + TIP) | Treatment H (Composite: SFS+TIP+SMS) | Delta (E vs A) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **MRR** | **Train** (210) | 0.3539 | **0.4544** | 0.4813 | **+0.1005** |
| | **Val** (60) | 0.1381 | **0.2971** | 0.2954 | **+0.1590** |
| | **Held-Out** (75) | 0.1290 | **0.2965** | 0.3115 | **+0.1675** |
| | **Overall** (345) | 0.2675 | **0.3927** | 0.4121 | **+0.1252** |
| **Hit@1** | **Train** (210) | 14.29% (30) | **25.71% (54)** | 28.57% (60) | **+11.42%** |
| | **Val** (60) | 0.00% (0) | **16.67% (10)** | 16.67% (10) | **+16.67%** |
| | **Held-Out** (75) | 1.33% (1) | **17.33% (13)** | 17.33% (13) | **+16.00%** |
| | **Overall** (345) | 8.99% (31) | **22.32% (77)** | 24.06% (83) | **+13.33%** |
| **Recall@20** | **Train** (210) | 0.7499 | **0.8009** | 0.8072 | **+0.0510** |
| | **Val** (60) | 0.5125 | **0.5875** | 0.6014 | **+0.0750** |
| | **Held-Out** (75) | 0.4133 | **0.5800** | 0.5889 | **+0.1667** |
| | **Overall** (345) | 0.6355 | **0.7157** | 0.7240 | **+0.0802** |
| **Seed Traps** | **Overall** (345) | 211 | **0** | 0 | **-211 (-100%)** |

**Conclusion**: The R2 figures reproduce bit-for-bit. Treatment E is confirmed as the stable reference baseline for Phase R3.

---

## 4. SEED-TRAP RECONCILIATION: R1 (259) VS R2 (211)

During Phase R1 forensic analysis, 259 queries were initially flagged as exhibiting rank-1 input seed traps. However, Phase R2 reported exactly 211 rank-1 seed traps.

### 4.1 Root Cause Breakdown
The 48-query discrepancy between R1 and R2 was audited line-by-line across all 345 queries:

1. **Traceback / Terminal Output Files (47 queries in `v2_trace2code`)**:
   - In R1, regex extractors aggressively parsed stack traces in terminal output (e.g. `File ".../core.py", line 123`).
   - In R2, `SeedExtractor` enforced strict, zero-oracle extraction rules targeting genuine input seed arguments (`seed_files`, diff header modified files, explicitly specified target modules).
   - Traceback lines often refer to third-party library internals or system paths that were not genuine query input seeds.
2. **Prose / PR Description Substrings (1 query)**:
   - A single query contained an incidental markdown substring that matched a repository path name in discussion text, but was not a seed parameter.

### 4.2 Reconciliation Summary
- **R1 Loose Heuristic Traps**: 259 queries (included traceback noise).
- **R2 Strict Zero-Oracle Traps**: **211 queries**.
- **Traps Eliminated by SFS**: **211 / 211 (100.0%)**.
- **Accidental Gold Suppressions**: **0 / 211 (0.0%)** (zero false suppressions).

This confirms the mathematical validity and engineering discipline of the R2 implementation.

---

## 5. FEATURE LINEAGE & ORACLE LEAKAGE AUDIT

The `TestIntentClassifier` and `TestIntentPrior` were audited to confirm zero data leakage:
- **No Ground-Truth Leakage**: The classifier does not inspect `gold_files`, benchmark suite names, track tags (`code2test`, `trace2code`, etc.), or commit messages.
- **Pure Lexical Inference**:
  - Positive patterns: `test`, `tests`, `unit test`, `integration test`, `test case`, `assert`, `fixture`, `spec`.
  - Negative patterns: `implement`, `fix bug`, `refactor`, `feature`, `documentation`.
- **Deterministic Calibration**: Feature weights and thresholds are statically configured constants evaluated only on query input text.

---

## 6. STATISTICAL INFERENCE METHODOLOGY AUDIT: REPOSITORY-CLUSTERED BOOTSTRAP

### 6.1 The Clustering Problem
In IR benchmarks spanning multiple software repositories, queries within the same repository share common naming conventions, dependency structures, and domain vocabularies. Treating each query as an independent and identically distributed (i.i.d.) observation artificially deflates standard errors and narrows confidence intervals.

### 6.2 Comparison of Resampling Strategies
To establish rigorous statistical standards for R3, we compared query-level bootstrap against repository-clustered bootstrap on the Validation split (5 repositories, 60 queries) for Treatment E vs Baseline M1:

- **Validation Observed Delta MRR**: $+0.1590$
- **Query-Level Bootstrap (10,000 resamples)**:
  - 95% Confidence Interval: **`[+0.0984, +0.2277]`**
  - Interval Width: $0.1294$
- **Repository-Clustered Bootstrap (10,000 resamples)**:
  - Resampling unit: Entire repository clusters (`['eslint/eslint', 'huggingface/diffusers', 'microsoft/playwright', 'pydantic/pydantic', 'tokio-rs/tokio']`).
  - 95% Confidence Interval: **`[+0.0170, +0.2195]`**
  - Interval Width: $0.2025$ (56.5% wider)
  - Empirical $P^*(\Delta \le 0) = 0.0094$ ($p < 0.01$).

### 6.3 Methodological Directive for R3
For all R3 statistical claims:
1. **Primary Uncertainty Metric**: Repository-clustered percentile confidence intervals (10,000 cluster resamples).
2. **Cluster Definition**: Cluster by repository snapshot to prevent intra-repository correlation from falsely inflating statistical significance.
3. **Hypothesis Testing**: Treatment effect is deemed statistically established only if the repository-clustered 95% CI strictly excludes zero ($\Delta > 0$).

---

## 7. SIGN-OFF AND BASELINE FREEZE

- **R2 Authoritative Champion**: Treatment E ($MRR_{\text{val}} = 0.2971$, $MRR_{\text{held\_out}} = 0.2965$).
- **Candidate Pool**: 514/514 gold candidates preserved (100.0% recall).
- **Audit Status**: VERIFIED, RECONCILED, AND FROZEN.
- **Authorization**: Proceed immediately to Part 1 (Data Governance) and R3 Implementation.

