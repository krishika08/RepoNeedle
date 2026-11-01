# Milestone 2 — Documentation & Statistical Terminology Correction Log

**Milestone**: M2 Recovery — Structural Ranking Reengineering  
**Scope**: Documentation & Reporting Audit across 345 Benchmark Queries (514 Gold Targets)  
**Date**: November 1, 2026  
**Auditor**: Independent Statistical Auditor & Principal Research Engineer  
**Branch**: `v1.0-zero-failure` (Frozen baseline `v0.1.0-release` protected)  
**Status**: Certified & Immutably Logged  

---

## 1. Executive Summary of Corrections

In accordance with independent statistical audit directives, this document records all documentation-only corrections applied across Milestone 2 reports.

### Strict Non-Modification Guarantees
- **No changes to M1 baseline metrics**: Micro Candidate Recall (1.0000), Macro Candidate Recall (1.0000), Complete-Gold Coverage (1.0000), MRR (0.2675), Hit@1 (0.0899), Micro Recall@20 (0.5953).
- **No changes to experimental configurations or code**: All ranking algorithms, bounded multipliers, and features remain identical.
- **No changes to raw evaluation data**: `frozen_m1_candidates.jsonl`, `PER_QUERY_RANK_MOVEMENTS.jsonl`, `M2_RECOVERY_RAW_RESULTS.jsonl`, and `m2_recovery_metrics_summary.json` remain untouched.
- **No changes to bootstrap resamples**: The 1,000 paired repository-clustered bootstrap iterations (seed = 42) remain preserved.
- **No changes to the final rejection decision**: Composite structural reranking, hub normalization, and Treatment F remain formally **REJECTED**; M1 remains the sole authoritative baseline; M3 is **NOT** started.

---

## 2. Itemized Documentation Corrections

### Correction 1: Bootstrap Interpretation & Statistical Terminology

#### Problem Identified:
Working drafts contained two statistical ambiguities:
1. Labeling $\hat{P}^*(\Delta^* \le 0)$ simply as a "p-value" implied a conventional frequentist null-hypothesis test.
2. A sentence suggested that the ordinary non-parametric bootstrap distribution approximates a Bayesian posterior distribution under flat uninformative priors.

#### Correction Applied:
1. **Removed Bayesian Posterior Statement**: Removed all references claiming the bootstrap distribution represents or approximates a Bayesian posterior distribution. A Bayesian posterior was **not calculated**.
2. **Precision in Bootstrap Tail Proportion Definition**:
   Defined $\hat{P}^*(\Delta^* \le 0)$ strictly as the **empirical bootstrap proportion of resampled treatment-effect estimates that are non-positive**:
   $$\hat{P}^*(\Delta^* \le 0 \mid \mathbf{X}) = \frac{1}{B} \sum_{b=1}^B \mathbb{I}(\Delta^{*(b)} \le 0)$$
   where $\Delta^{*(b)}$ represents the paired treatment-minus-baseline difference in the $b$-th cluster-bootstrap replicate ($B = 1,000$).
3. **Explicit Frequentist Distinction**:
   Explicitly stated that $\hat{P}^*(\Delta^* \le 0)$ is **not a conventional frequentist null-hypothesis $p$-value**, because unshifted bootstrap draws are centered at the observed sample estimate $\hat{\Delta}$, not at $H_0: \Delta = 0$.
4. **Primary Uncertainty Framework**:
   Confirmed that the **preregistered 95% percentile confidence intervals** ($\text{CI}_{95\%} = [q^*_{0.025}, \, q^*_{0.975}]$) are the official uncertainty bounds.
5. **Statistical Disposition of Treatment F**:
   Formally recorded that **Treatment F is not statistically established as an improvement** over the frozen M1 baseline because its 95% bootstrap confidence intervals for both MRR ($[-0.00114, +0.00975]$) and Recall@20 ($[-0.00130, +0.01600]$ for Macro, $[-0.00195, +0.00778]$ for Micro) strictly contain zero.

---

### Correction 2: Structural Expansion Counting Units & Denominator Audit

#### Problem Identified:
Working drafts cited a "98.6% false-positive rate" based on the ratio $340 / 345 = 98.55\%$. Because the benchmark coincidentally contains 345 queries, readers risked conflating the denominator 345 with benchmark queries or unique gold seeds.

#### Audit of Counting Units:
A complete traversal of all 7,149 candidate evidence edges across all 345 queries in `frozen_m1_candidates.jsonl` verified the exact counts:

1. **Edge-Level Counting Unit (340 / 345)**:
   - **Total candidate evidence edges**: 7,149 edges.
   - **Edges originating from an annotated gold target seed**: Exactly **345 edges**. (Coincidentally equal to the 345 benchmark queries, but measuring candidate expansion edges).
   - **Edges from gold seeds pointing to an annotated gold target**: **5 edges**.
   - **Edges from gold seeds pointing to a non-gold target**: **340 edges**.
   - **Correct Edge-Level Metric**:
     $$\text{Non-Gold Expansion Edge Proportion} = \frac{340 \text{ non-gold expansion edges from gold seeds}}{345 \text{ total expansion edges from gold seeds}} = \mathbf{98.5507\%} \quad (\approx 98.55\%)$$
     $$\text{Gold-Coupled Expansion Edge Proportion} = \frac{5 \text{ gold-coupled edges from gold seeds}}{345 \text{ total expansion edges from gold seeds}} = \mathbf{1.4493\%} \quad (\approx 1.45\%)$$

2. **Seed-Level Counting Unit (138 / 142)**:
   - Across the 345 queries, exactly **142 unique gold query-seed instances** triggered candidate expansion.
   - **138 gold seeds** produced $\ge 1$ candidate expansion edge pointing to a non-gold target.
   - **5 gold seeds** produced $\ge 1$ candidate expansion edge pointing to an annotated gold target.
   - **Correct Seed-Level Metric**:
     $$\text{Proportion of Gold Seeds Producing } \ge 1 \text{ Non-Gold Expansion} = \frac{138}{142} = \mathbf{97.1831\%} \quad (\approx 97.18\%)$$
     $$\text{Proportion of Gold Seeds Producing } \ge 1 \text{ Gold Expansion} = \frac{5}{142} = \mathbf{3.5211\%} \quad (\approx 3.52\%)$$

3. **Terminology Correction**:
   - Replaced "false positive rate" with **"Non-Gold Expansion Edge Proportion"** (edge-level) and **"Proportion of gold seeds producing at least one non-gold expansion"** (seed-level).
   - Clarified that this audit represents a **diagnostic oracle-seeded expansion analysis** starting from ground-truth gold targets, distinct from production inference where gold targets are unknown.
   - Clarified that expanded non-gold files are valid structural couplings in the repository graph, but are task-irrelevant under the specific benchmark query's resolution annotation.

---

### Correction 3: Repository Cluster Reconciliation (25 vs 21 Clusters)

#### Problem Identified:
Earlier reports contained the text:
> *"1,000 resamples clustered at repository boundary (21 clusters)."*
However, the ARB v2 benchmark contains 25 repositories.

#### Audit & Resolution:
1. **Code Execution Audit**:
   Inspected `eval_m2.py` and `execute_m2_recovery_full.py`. In both scripts, cluster assignment was performed dynamically:
   ```python
   clusters = defaultdict(list)
   for idx, r in enumerate(baseline_records):
     clusters[r["repo"]].append(idx)
   cluster_keys = list(clusters.keys())
   k = len(cluster_keys)
```
   In runtime execution, `len(cluster_keys)` evaluated to **25**. The code resampled with replacement across all $k = 25$ repository clusters.
2. **Identification of Root Cause**:
   The string `"(21 clusters)"` was an unedited copy-paste documentation artifact from earlier project phases (Stage 3.7 / 3.8 / early ContextBench), which operated on an older 21-repository evaluation scope.
3. **Cluster Invariants Confirmed**:
   - All 25 repositories were included in the resampling pool (0 excluded).
   - Every one of the 345 queries was partitioned into exactly one repository cluster (0 overlaps, 0 omissions).

---

### Correction 4: Reaffirmation of Final M2 Disposition

#### Confirmation of Invariants:
1. **Rejection of Composite Structural Reranking**: All composite structural rerankers (`m2_full_auto`, `m2a`–`m2e`) remain permanently rejected due to catastrophic precision degradation.
2. **Rejection of Hub Normalization**: Treatment B (`m1_hub_norm`) remains rejected due to statistically significant MRR degradation ($\Delta \text{MRR} = -0.0063$, 95% CI: $[-0.0113, -0.0003]$, 51 losses).
3. **Rejection of Treatment F for Production**: Treatment F remains rejected because its 95% bootstrap confidence intervals span zero, failing to prove statistically significant superiority.
4. **Authoritative Baseline Maintained**: The frozen M1 candidate retrieval engine remains the sole authoritative production baseline.
5. **No Advancement to M3**: Milestone 2 is formally closed. Milestone 3 has **NOT** been started.

---

## 3. Inventory of Affected Documents & Verified Changes

| Document Path | Section(s) Corrected | Changes Applied |
| :--- | :--- | :--- |
| [`research/v1_accuracy/m2_recovery/M2_STATISTICAL_RECONCILIATION.md`](file:///F:/RepoNeedle/research/v1_accuracy/m2_recovery/M2_STATISTICAL_RECONCILIATION.md) | Section 2.2, Section 4 | Removed Bayesian posterior text; defined $\hat{P}^*(\Delta^* \le 0)$ as empirical bootstrap tail proportion; fully articulated edge-level (340/345) and seed-level (138/142) metrics. |
| [`research/v1_accuracy/m2_recovery/STRUCTURAL_EVIDENCE_AUDIT.md`](file:///F:/RepoNeedle/research/v1_accuracy/m2_recovery/STRUCTURAL_EVIDENCE_AUDIT.md) | Section 1, Section 3 | Clarified diagnostic oracle-seeded analysis; separated Edge-Level Non-Gold Proportion (340/345 = 98.55%) from Seed-Level Proportion (138/142 = 97.18%). |
| [`research/v1_accuracy/m2_recovery/RERANKER_ABLATION_RESULTS.md`](file:///F:/RepoNeedle/research/v1_accuracy/m2_recovery/RERANKER_ABLATION_RESULTS.md) | Section 4 (Table) | Replaced "$p$-value" column with $\hat{P}^*(\Delta^* \le 0)$; added statistical footnote; labeled $\Delta \text{Macro Rec@20}$. |
| [`research/v1_accuracy/m2_recovery/M2_RECOVERY_DECISION.md`](file:///F:/RepoNeedle/research/v1_accuracy/m2_recovery/M2_RECOVERY_DECISION.md) | Section 2, Section 3 | Replaced "$p$-value" with $\hat{P}^*(\Delta^* \le 0)$; aligned edge-level expansion wording (340/345 edges). |
| [`research/v1_accuracy/m2_structural_ranking/M2_DECISION_REPORT.md`](file:///F:/RepoNeedle/research/v1_accuracy/m2_structural_ranking/M2_DECISION_REPORT.md) | Section 2, Section 3, Section 4 | Removed claim accepting hub normalization prior; corrected "21 clusters" copy-paste artifact; formally closed M2 with baseline lock. |

---

## 4. Final Sign-off

- **Audit Completion**: All statistical documentation discrepancies have been fully reconciled and verified.
- **Experimental Integrity**: 100% preserved. No code, configuration, or experimental data was modified.
- **Milestone 2**: **FORMALLY CLOSED**.

