# RepoNeedle Stage 3.9.2: Decision & Gate Authorization Report

**Document ID**: `STAGE3.9.2-DECISION-001`  
**Date**: October 2026  
**Auditor**: Independent Reproducibility & Benchmark Integrity Auditor  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Audited Commit**: `b7cf35bc6ebfebc7e6c6cc5df122118bdb1c3bbc`  
**Decision**: **PASS WITH LIMITATIONS**  
**Authorization for Stage 3.10**: **GRANTED UNDER CONSTRAINTS**

---

## 1. Executive Gate Decision

Stage 3.9.2 has successfully audited, reconciled, and documented all reported metric discrepancies across Stage 3.5, Stage 3.6, Stage 3.9, and Stage 3.9.1. 

We formally render the verdict: **PASS WITH LIMITATIONS**.

The gate authorization for Stage 3.10 (Class-to-Test Invocation Graph Research) is **GRANTED**, subject to strict adherence to the [Canonical Evaluation Contract v1.0.0](file:///F:/RepoNeedle/research/stage3_9_2/CANONICAL_EVALUATION_CONTRACT.md).

---

## 2. Exit Criteria Verification Matrix

| Exit Criterion | Required Condition | Audit Verification & Findings | Criterion Status |
| :--- | :--- | :--- | :---: |
| **1. Discrepancy Reconciliation** | Reconcile Stage 3.5 vs Stage 3.9.1 discrepancies across BM25, RepoMap, CAND-C, and CAND-F. | Every discrepancy investigated, mathematically accounted for, and recorded in [`DISCREPANCY_MATRIX.csv`](file:///F:/RepoNeedle/research/stage3_9_2/DISCREPANCY_MATRIX.csv) and [`CROSS_STAGE_METRIC_AUDIT.md`](file:///F:/RepoNeedle/research/stage3_9_2/CROSS_STAGE_METRIC_AUDIT.md). | **MET** |
| **2. Architecture Comparability** | Confirm whether Candidate C and Candidate F represent comparable configurations across stages. | Fully documented: Stage 3.5 evaluated filtered candidate pools with diagnostic shortcuts; Stage 3.6+ evaluated full unconstrained repositories without shortcuts. Version/naming boundaries made explicit. | **MET** |
| **3. Budget Ambiguity Removal** | Unambiguously distinguish character-based and tokenizer-based budget metrics. | Fully separated: Character-based greedy stop (`0.0493`) isolated from token-based boundary truncation (`0.2286`) and skeleton knapsack (`0.2431`). Prohibited unqualified `BCY@8k`. | **MET** |
| **4. Deterministic Packing Tests** | Document context-packing policies and cover with deterministic unit tests. | 7 comprehensive unit tests created in [`tests/test_stage3_9_2_budget_audit.py`](file:///F:/RepoNeedle/tests/test_stage3_9_2_budget_audit.py); 100% passing across all edge cases, tie-breaking, and boundary limits. | **MET** |
| **5. Statistical & Latency Reproducibility** | Verify statistical calculations, bootstrap CIs, Wilcoxon tests, and latency profiling from retained artifacts. | Complete verification in [`STATISTICAL_AND_LATENCY_AUDIT.md`](file:///F:/RepoNeedle/research/stage3_9_2/STATISTICAL_AND_LATENCY_AUDIT.md). Dissected query-level vs clustered CIs and exposed historical static latency constants. | **MET** |
| **6. Canonical Contract Alignment** | The canonical evaluation contract and final discrepancy matrix agree with executable implementation. | Formulated [`CANONICAL_EVALUATION_CONTRACT.md`](file:///F:/RepoNeedle/research/stage3_9_2/CANONICAL_EVALUATION_CONTRACT.md) v1.0.0. All 133 repository unit tests pass. | **MET** |

---

## 3. The Specific "Limitations" Defined

The verdict is designated **PASS WITH LIMITATIONS** due to two critical experimental boundaries that must be recognized:

1. **Development Benchmark Boundary (ARB v2)**:
   All canonical claims are established on the ARB v2 development corpus ($N = 345$ positive queries across 25 repositories). Because the official **ContextBench** benchmark acquisition remains blocked by network and authentication boundaries, these metrics constitute **developmental and regression evidence, NOT independent proof of out-of-distribution generalization**.
2. **Subgroup Exploratory Status**:
   While `CAND-CASCADE` demonstrates decisive macro superiority over BM25 ($+7.77\%$, $p = 8.22 \times 10^{-40}$) and recovers $+42.4\%$ over Candidate F, its leads over RepoMap on specific tracks (`comment2context`, `edit2ripple`) are exploratory subgroup findings. Pinned RepoMap maintains the aggregate macro lead ($0.2293$ vs. $0.1905$) driven by `code2test`.

---

## 4. Binding Directives for Stage 3.10

Stage 3.10 (Class-to-Test Invocation Graph Research) may now proceed under the following non-negotiable rules:

1. **Preserve Pinned Baselines**:
   - `BASE-BM25` ground truth is strictly **$0.1768$ MRR** (decoupled).
   - `BASE-REPOMAP` ground truth is strictly **$0.2293$ MRR** (pinned commit `9e4d689`).
   - `CAND-CASCADE` baseline is strictly **$0.1905$ MRR**.
2. **Do Not Relabel Hit Rate as Recall**:
   Fractional multi-target Recall@20 ($0.4622$ for BM25, $0.5503$ for Cascade) must be reported separately from binary Hit@20 ($0.5391$ for BM25, $0.6377$ for Cascade).
3. **Budget Reporting Standards**:
   All context-packing numbers must declare the unit (`char` vs. `token`) and the policy (`greedy_stop`, `greedy_skip`, `boundary_truncation`, or `skeleton_knapsack`).
4. **Preserve Immutable Frozen Tags**:
   - `v0.1.0-baseline` must point to `8e0042553a14b6e3c6cf5b35823c4da84181a8e9`.
   - `stage3-candidate-freeze` must point to `cd7f3b01e28695f9a9357e0815069e0eae85baca`.
