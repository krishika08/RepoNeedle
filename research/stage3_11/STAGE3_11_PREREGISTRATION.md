# RepoNeedle Stage 3.11: Function-Level Graph Retrieval Research — Preregistration

**Date**: October 29, 2026  
**Stage**: Stage 3.11  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Anchor Commit**: `768f69d` (Stage 3.10.2 Canonical Evaluation Integrity Gate)  
**Status**: FORMALLY LOCKED PRIOR TO BENCHMARK EXECUTION  

---

## 1. Research Question and Hypotheses

### Background
Stage 3.10.2 reproduced and certified the canonical evaluation results over all 345 positive ARB v2 queries:
- `BASE-BM25`: 0.1752 MRR, 0.5487 Recall@20
- `CONTROL-CASCADE`: 0.1883 MRR, 0.5574 Recall@20
- `TEST-GRAPH`: 0.1898 MRR, 0.5605 Recall@20
- `BASE-REPOMAP`: 0.2293 MRR, 0.6599 Recall@20

While `TEST-GRAPH` was statistically superior to `CONTROL-CASCADE` ($p = 0.000964$), **90.7% of all queries (313/345) resulted in exact ties**. Forensic inspection revealed that `TEST-GRAPH` only modelled class-to-test invocations, leaving inter-file and intra-file production function-to-function call relationships entirely unmodelled.

### Primary Hypothesis (H1)
Augmenting `CONTROL-CASCADE` with a conservative, language-aware function-level call graph (`FUNCTION-GRAPH`) increases candidate discovery between interacting production files, achieving at least a **2.0% relative improvement in MRR** over `CONTROL-CASCADE` ($\text{MRR} \ge 0.1921$) under the canonical unconstrained candidate pool, while maintaining non-inferior Recall@20.

### Secondary Hypotheses
- **H2 (Edge Precision)**: Verified call edges with qualifying imports (`FUNCTION-GRAPH-VERIFIED`) achieve higher precision and lower graph pollution than unverified structural heuristic edges.
- **H3 (Lexical Safeguard Integrity)**: Preserving the Rank 1–3 BM25 lexical freeze is essential; relaxing or removing the freeze (`FUNCTION-GRAPH-NO-FREEZE`) causes rank displacement on strong lexical queries and degrades aggregate MRR.
- **H4 (Domain Specificity)**: Function-level call edges specifically improve mechanism-targeted tasks (`trace2code`, `edit2ripple`, and `code2test`) without degrading `comment2context`.

---

## 2. Experimental Arms and Baseline Systems

The benchmark evaluates the following 9 systems under identical conditions:

1. **`BASE-BM25`**: Decoupled length-normalized Okapi BM25 with deterministic alphabetical tie-breaking.
2. **`CONTROL-CASCADE`**: Stage 3.10 Arm A control architecture (Rank 1–3 BM25 freeze, package boundary fencing, degree normalization).
3. **`TEST-GRAPH`**: Stage 3.10 Arm B (Class-to-Test invocation graph).
4. **`DEGREE-CONTROL`**: Stage 3.10 Arm C (Degree-matched randomized graph control).
5. **`BASE-REPOMAP`**: Pinned official RepoMap baseline (commit `9e4d689`).
6. **`FUNCTION-GRAPH`**: Full function-level graph (verified call edges + structural method edges) integrated into `CONTROL-CASCADE` with Rank 1–3 freeze.
7. **`FUNCTION-GRAPH-VERIFIED`**: Function-level graph restricted strictly to Level-1 verified call edges (qualifying module imports, intra-file calls, and unique repository function names).
8. **`FUNCTION-GRAPH-ABLATION`**: Function-level graph with lower-confidence structural dependency edges ablated.
9. **`FUNCTION-GRAPH-NO-FREEZE`**: Function-level graph with the Rank 1–3 freeze relaxed, evaluating whether graph propagation can safely reorder top lexical candidates.

---

## 3. Candidate Pool and Query-Time Safeguards

1. **100% Unconstrained Candidate Universe**: Every query ranks against the complete file set of its repository snapshot. Zero candidate pre-filtering by task type, path prefix, or gold label.
2. **Strict Query-Time Information Isolation**: No gold-label paths, task classifications, or target file counts are accessible during index construction, symbol extraction, or graph propagation.
3. **Deterministic Execution**: All tie-breaking is strictly alphabetical by normalized document path. Fixed random seed $42$ for degree-matched controls and bootstrap resampling.
4. **Development/Regression Benchmark Status**: ARB v2 is formally designated as a development and regression suite. Results do not constitute evidence of independent generalization.

---

## 4. Evaluation Metrics and Definitions

### Primary Metric
- **Mean Reciprocal Rank (MRR)**: Average reciprocal rank of the first retrieved gold file across all 345 positive queries.

### Secondary Metrics
- **Fractional Recall@20**: Average proportion of gold files retrieved in the top 20 candidates.
- **Binary Hit@20**: Proportion of queries with at least one gold file in the top 20.
- **Precision@5**: Proportion of retrieved top-5 files that are gold targets.
- **Context Coverage (`char_cov@8k`)**: Greedy-stop chunk character coverage at 8,000 characters.
- **Token BCY (`token_bcy@8k`)**: Token-budgeted gold file coverage at 8,000 tokens using `regex_code_tokenizer_v1`.
- **Latency**: Median (p50) and 95th percentile (p95) warm query latency in milliseconds.
- **Process Memory**: Process RSS and peak working set in megabytes measured via native Win32 `GetProcessMemoryInfo`.
- **Abstention / Selective Retrieval**: Hit rate and false positive rate on the 82 no-gold queries evaluated separately.

---

## 5. Statistical Protocol

1. **Paired Differences**: All comparisons are paired at the query level against `CONTROL-CASCADE`.
2. **Bootstrap Confidence Intervals**: 10,000 bootstrap resamples with seed 42:
   - Primary: Repository-clustered bootstrap (preserving the 25 repository groupings).
   - Supplementary: Query-level bootstrap ($N = 345$).
3. **Significance Testing**: Two-sided Wilcoxon signed-rank test computed on non-zero paired differences.
4. **Multiple Comparison Correction**: Holm-Bonferroni step-down adjustment across planned comparisons:
   - `FUNCTION-GRAPH` vs. `CONTROL-CASCADE`
   - `FUNCTION-GRAPH-VERIFIED` vs. `CONTROL-CASCADE`
   - `FUNCTION-GRAPH-ABLATION` vs. `CONTROL-CASCADE`
   - `FUNCTION-GRAPH-NO-FREEZE` vs. `CONTROL-CASCADE`
   - `FUNCTION-GRAPH` vs. `TEST-GRAPH`
   - `FUNCTION-GRAPH` vs. `BASE-REPOMAP`
5. **Practical Effect Size**: Formal evaluation of win/loss/tie ratios, mean gain per affected query, and proportion of active (non-tie) queries.

---

## 6. Pre-Registered Acceptance Gate

To pass the Stage 3.11 gate and qualify for promotion, a candidate variant must satisfy **all 7 criteria**:

1. **Relative MRR Gain**: $\ge +2.0\%$ relative improvement over `CONTROL-CASCADE` ($\Delta\text{MRR} \ge +0.0038$, target $\text{MRR} \ge 0.1921$).
2. **Uncertainty Gate**: The 95% repository-clustered bootstrap confidence interval for $\Delta\text{MRR}$ must strictly exclude zero.
3. **Recall Non-Inferiority**: Fractional Recall@20 must not degrade by more than $0.5$ percentage points compared to `CONTROL-CASCADE` ($\Delta\text{Recall@20} \ge -0.0050$).
4. **Repository Diversity**: Benefit must be observed across multiple repositories and not be an artifact of a single outlier repository.
5. **Protocol Compliance**: 100% unconstrained candidate pool, zero query-time leakage, distinct budget units.
6. **Resource Bound**: Median warm query latency $< 25.0\text{ ms}$, cold index construction $< 200\text{ ms}$, process RSS scalable with codebase size.
7. **Regression and Integrity**: All existing repository tests pass, all new Stage 3.11 tests pass, deterministic reproduction verified.

