# REPONEEDLE MISSION 0.80+ — PHASE R3
# DELIVERABLE 10: REPOSITORY-CLUSTERED STATISTICAL VALIDATION REPORT

**Author**: Principal Information Retrieval Engineer, Lead Statistician  
**Date**: November 2, 2026  
**Status**: APPROVED & FROZEN  
**Target Milestone**: Phase R3 (AST Symbol Intelligence + BM25L Ranking)  

---

## 1. INFERENCE METHODOLOGY & FORMAL DEFINITIONS

To prevent intra-repository correlations from producing falsely optimistic confidence intervals, statistical significance is evaluated using **Repository-Clustered Bootstrap Resampling** with 10,000 Monte Carlo iterations.

### 1.1 Mathematical Definitions
Let $R = \{r_1, r_2, \dots, r_M\}$ be the set of distinct repositories in evaluation split $S$.
In each bootstrap iteration $b \in \{1, \dots, 10000\}$:
1. Resample $M$ repositories with replacement: $R^{(b)} = (r_1^{(b)}, \dots, r_M^{(b)})$.
2. Collect all queries belonging to $R^{(b)}$: $Q^{(b)} = \bigcup_{r \in R^{(b)}} Q(r)$.
3. Compute the resampled treatment effect:
   $$\Delta^{*(b)} = \text{MRR}_I(Q^{(b)}) - \text{MRR}_A(Q^{(b)})$$
4. The empirical percentile confidence interval is:
   $$\text{CI}_{95\%} = [\Delta^*_{2.5\%}, \Delta^*_{97.5\%}]$$
5. The empirical non-positive proportion is:
   $$P^*(\Delta^* \le 0) = \frac{1}{B} \sum_{b=1}^B \mathbb{I}(\Delta^{*(b)} \le 0)$$

---

## 2. STATISTICAL VALIDATION RESULTS

The statistical evaluation was executed via `research/v1_accuracy/ranking_0_80/r3/src/statistical_validation.py`.

### 2.1 Master Uncertainty & Significance Summary

| Evaluation Split | Repos | Queries | Baseline A MRR | Champion I MRR | Observed $\Delta$ | Repository-Clustered 95% CI | Clustered Width | Empirical $P^*(\Delta^* \le 0)$ | Query-Level 95% CI | Permutation $p$-value |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Validation** | 5 | 60 | 0.2971 | **0.3124** | **+0.0153** | **`[-0.0326, +0.0330]`** | 0.0656 | 0.2906 | `[-0.0079, +0.0413]` | $p = 0.2502$ |
| **Training** | 15 | 210 | 0.4544 | **0.5278** | **+0.0734** | `[-0.0795, +0.2348]` | 0.3143 | 0.1574 | `[+0.0362, +0.1111]` | $p = 0.0001$ |
| **Held-Out** | 5 | 75 | **0.2965** | 0.2835 | -0.0129 | `[-0.0668, -0.0035]` | 0.0633 | 1.0000 | `[-0.0586, +0.0286]` | $p = 0.5977$ |

---

## 3. STATISTICAL INTERPRETATION & AUDIT FINDINGS

### 3.1 Comparison of Resampling Strategies
1. **Query-Level vs Repository-Clustered CI on Validation**:
   - Query-level bootstrap reports interval `[-0.0079, +0.0413]` (width: 0.0493).
   - Repository-clustered bootstrap reports interval `[-0.0326, +0.0330]` (width: 0.0656, 33.1% wider).
   - The clustered interval properly captures the high variance across individual codebases (`tokio` gained $+0.0337$, whereas `diffusers` lost $-0.0200$).

### 3.2 Evaluation of the Treatment Effect
- On the Validation split, the observed point improvement is $+0.0153$ MRR (+5.15% relative), with Hit@1 increasing from 16.67% to 18.33%.
- However, the 95% repository-clustered confidence interval strictly includes zero ($[-0.0326, +0.0330]$), with $P^*(\Delta^* \le 0) = 0.2906$.
- Furthermore, on the Held-Out confirmation split, Treatment I experiences a mild regression of $-0.0129$ MRR ($0.2965 \to 0.2835$).
- **Conclusion**: The treatment effect does not satisfy the strict threshold of generalizable repository-invariant improvement.

---

## 4. CANDIDATE POOL RECALL AUDIT

To ensure that ranking adjustments never compromise search completeness:
- **Total Gold Targets in Universe**: 514 files.
- **Recovered Gold Targets in Ranked Candidates**: **514 / 514 (100.00%)**.
- **Candidate Pool Loss**: **0 gold targets lost**.

