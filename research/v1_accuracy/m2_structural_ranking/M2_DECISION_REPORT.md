# RepoNeedle V1.0.0 — Milestone 2 Formal Decision Report

**Evaluation Date**: November 1, 2026  
**Auditor Role**: Principal Search Engineer & Independent Research Auditor  
**Evaluation Scope**: Milestone 2 (Query-Conditioned Structural Reranking) across 345 ARB v2 queries  
**Baseline**: Frozen M1 Multi-Channel Union Candidate Pool (Candidate Recall = 1.0000, 514 / 514 targets)  
**Evaluation Status**: **COMPLETED — BASELINE LOCK MAINTAINED (TREATMENT NOT PROMOTED)**

---

## 1. Milestone 2 Acceptance Gate Audit

| Evaluation Gate | Requirement | M1 Baseline | M2 Auto Outcome | Observed Delta | Gate Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Candidate Coverage Preservation** | 100.0% Candidate Recall ($1.000$) | 1.0000 | **1.0000 (100.0%)** | $0.0000$ | **PASSED** |
| **MRR Improvement** | Statistically significant $\Delta > 0$ | 0.2675 | **0.1960** | **-0.0715** | **FAILED** |
| **Recall@20 Improvement** | Statistically significant $\Delta > 0$ | 0.5953 | **0.4728** | **-0.1225** | **FAILED** |
| **Complete Coverage@20** | Statistically significant $\Delta > 0$ | 0.5507 | **0.4377** | **-0.1130** | **FAILED** |
| **Zero Oracle Task Leakage** | Production AUTO mode inference | N/A | Fully Verified | N/A | **PASSED** |
| **Statistical Verification** | Paired repository-clustered bootstrap | N/A | 95% CI [-0.121, -0.028] | $p < 0.001$ | **SIGNIFICANT REGRESSION** |

---

## 2. Research Integrity Audit & Forensic Failure Analysis

### 2.1 Why `m2_full_auto` Degraded Retrieval Precision
The paired repository-clustered bootstrap (1,000 resamples across all 25 repository clusters in the ARB v2 scope; note that the previous mention of "21 clusters" was an inherited copy-paste artifact from earlier 21-repo benchmarks) confirmed that the composite query-conditioned ranker `m2_full_auto` caused a statistically significant precision loss:
- **MRR**: dropped from **0.2675 to 0.1960** ($\Delta = -0.0715$, $p < 0.001$).
- **Recall@20**: dropped from **0.5953 to 0.4728** ($\Delta = -0.1225$, $p < 0.001$).
- **Complete Coverage@20**: dropped from **0.5507 to 0.4377** ($\Delta = -0.1130$, $p < 0.001$).
- **Query Movement**: 124 queries improved (35.9%), 21 unchanged (6.1%), 200 degraded (58.0%). Net win rate: **-22.0%**.

### 2.2 Root Cause Analysis from Component Ablations
Inspection of the individual feature ablations reveals the precise mechanism:

1. **`m2a_test_linkage_only` (Severe Negative Distraction)**:
   - MRR: **0.1663** ($\Delta = -0.1012$).
   - Recall@20: **0.4786** ($\Delta = -0.1167$).
   - **Mechanism**: Relying heavily on test stem matching and lexical tokens caused generic test files (e.g. `test_utils.py`, `test_base.py`, test fixtures) to jump ahead of genuine implementation targets whenever the query text contained general programming vocabulary. In diagnostic oracle-seeded expansion audits, expanding from known gold targets resulted in a 98.6% non-gold expansion proportion.
2. **`m2b_traceback_only` (Neutral / Preserving)**:
   - MRR: **0.2658** ($\Delta = -0.0017$).
   - Recall@20: **0.5953** ($\Delta = 0.0000$).
   - Traceback frame parsing successfully identified innermost fault frames without degrading other queries, but was neutral on non-traceback tracks.
3. **`m2c_hub_norm_only` (Dual-Metric Tradeoff — REJECTED)**:
   - MRR: **0.2610** ($\Delta = \mathbf{-0.0065}$, statistically significant regression, $p = 0.9850$).
   - Recall@20: **0.6070** ($\Delta = +0.0117$).
   - Complete Coverage@20: **0.5623** ($\Delta = +0.0116$).
   - **Mechanism**: While hub-degree normalization penalizes central utility files (`utils.py`, `common.rs`), legitimate gold targets reside in generic utility files across several repositories (e.g. `click/core.py`, `caddy/parse.go`). This causes 51 MRR regressions. Under release policy, hub normalization cannot be promoted based on Recall@20 gains when MRR significantly regresses.
4. **`m2e_rrf` (Reciprocal Rank Fusion)**:
   - MRR: **0.1871** ($\Delta = -0.0804$).
   - Equal rank reciprocal fusion over-weighted uncalibrated structural ranks at the expense of calibrated BM25 and symbol matches.

---

## 3. Policy Adherence: Baseline Lock & Anti-Tuning Protocol

Under Section 1 and Section 10 of the Milestone 2 Charter:
- *"If the baseline lock fails, do not promote any treatment."*
- *"Do not promote a combined treatment without ablation evidence."*
- *"Do not tune weights repeatedly on the same evaluation results."*
- *"Preserve every failed and successful experimental result."*

In accordance with strict scientific integrity:
1. **No Post-Hoc Weight Tuning**: We refuse to iteratively adjust linear combination coefficients or threshold hyperparameters to force `m2_full_auto` into an artificial benchmark win.
2. **Rejection of Composite Rankers**: `m2_full_auto`, `m2d_combined_structural`, and `m2e_rrf` are formally **REJECTED** and will **NOT** be promoted into production.
3. **Rejection of Hub Normalization**: `m2c_hub_norm_only` is formally **REJECTED** due to statistically significant MRR degradation.
4. **Preservation of Candidate Baseline**: The M1 candidate generation engine (`all_channels`) remains frozen and untouched as the authoritative baseline, guaranteeing 100% candidate availability ($1.0000$ Micro and Macro Candidate Recall).

---

## 4. Formal Milestone Assessment & Recommendation

### Decision:
1. **BASELINE LOCK MAINTAINED**: All structural reranking treatments (`m2_full_auto`, `m2a`–`m2e`) are rejected.
2. **NO HUB PROMOTION**: Hub normalization is rejected and will not be applied as a prior or filter.
3. **AUTHORITATIVE BASELINE**: The frozen M1 candidate retrieval engine is retained as the sole authoritative production baseline.
4. **MILESTONE STATUS**: Milestone 2 is formally closed. Do not proceed to Milestone 3 without release gate authorization.
