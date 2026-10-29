# RepoNeedle Stage 3.9.1: Statistical Verification & Paired Resampling Audit

**Document ID**: `STAGE3.9.1-STAT-001`  
**Date**: October 2026  
**Auditor**: Independent Reproducibility & Benchmark Integrity Auditor  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Sample Population**: $N = 345$ positive ARB v2 queries across $K = 25$ repositories (218 snapshots)  
**Dataset**: [`research/stage3_9_1/INDEPENDENT_RECOMPUTATION.csv`](file:///f:/RepoNeedle/research/stage3_9_1/INDEPENDENT_RECOMPUTATION.csv) ($2,415$ rows)  

---

## 1. Executive Summary

This audit performs an independent verification of the statistical claims made in Stage 3.9. We evaluate paired differences between `CAND-CASCADE` and its primary baselines (`BASE-BM25`, `CAND-F`, and `BASE-REPOMAP`) computed directly from the 2,415 raw tall-format evaluation rows.

To ensure statistical rigor, we report both **Unclustered (Query-Level) Bootstrap** and **Repository-Clustered Bootstrap** ($B = 10,000$ iterations, random seed = 42), alongside the non-parametric **Wilcoxon signed-rank test** ($p$-value with Pratt zero-handling).

---

## 2. Statistical Methodology

### 2.1 Paired Differences
For each query $i \in \{1, \dots, N\}$, the paired difference is:
$$\Delta_i = \text{MRR}_{\text{target}, i} - \text{MRR}_{\text{base}, i}$$
The sample mean difference is $\bar{\Delta} = \frac{1}{N} \sum_{i=1}^N \Delta_i$. Relative percentage improvement is calculated against the baseline mean:
$$\text{Rel} \% = \frac{\bar{\Delta}}{\overline{\text{MRR}}_{\text{base}}} \times 100\%$$

### 2.2 Clustered Bootstrap Resampling
When benchmark queries originate from a finite set of $K = 25$ repositories, queries within the same repository are not independent. Under repository clustering:
1. At each iteration $b \in \{1, \dots, B\}$, draw $K = 25$ repositories with replacement from the set of unique repositories.
2. Form the bootstrap sample by taking all queries belonging to the selected repositories:
   $$\bar{\Delta}^*_b = \frac{\sum_{k \in \text{selected}} \sum_{i \in \text{repo}_k} \Delta_i}{\sum_{k \in \text{selected}} |\text{repo}_k|}$$
3. Construct the 95% Confidence Interval using the 2.5th and 97.5th percentiles of $\{\bar{\Delta}^*_1, \dots, \bar{\Delta}^*_B\}$.

---

## 3. Empirical Results & Paired Comparison Matrix

### Table 1: Paired Statistical Comparison ($N = 345, K = 25, B = 10,000$, Seed = 42)

| Comparison | Target System | Baseline System | Mean Baseline MRR | Mean Target MRR | Mean Delta ($\bar{\Delta}$) | Relative Change (%) | Query-Level 95% CI | Repo-Clustered 95% CI | Wilcoxon Signed-Rank $p$ | Significant at $\alpha=0.01$? |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| **Cascade vs. BM25** | CAND-CASCADE | BASE-BM25 | 0.1768 | 0.1905 | **+0.0137** | **+7.77%** | $[+0.0108, +0.0169]$ | **$[+0.0111, +0.0166]$** | $8.22 \times 10^{-40}$ | **YES** |
| **Cascade vs. Candidate F** | CAND-CASCADE | CAND-F | 0.1338 | 0.1905 | **+0.0567** | **+42.41%** | $[+0.0355, +0.0784]$ | $[-0.0079, +0.1033]$ | $1.09 \times 10^{-14}$ | **YES** (Query-paired) |
| **Cascade vs. RepoMap** | CAND-CASCADE | BASE-REPOMAP | 0.2293 | 0.1905 | **-0.0387** | **-16.90%** | $[-0.0716, -0.0057]$ | $[-0.0915, +0.0030]$ | $9.03 \times 10^{-4}$ | **NO** (RepoMap leads) |

---

## 4. Detailed Analysis of Findings

### 4.1 CAND-CASCADE vs. BASE-BM25
- The mean MRR improvement is $+0.0137$ (+7.77% relative gain).
- Both the query-level CI ($[+0.0108, +0.0169]$) and the repository-clustered CI ($[+0.0111, +0.0166]$) are **strictly positive and bounded away from zero**.
- The Wilcoxon signed-rank test yields $p = 8.22 \times 10^{-40}$, confirming that the improvement over BM25 is statistically significant and robust across repository clusters.
- Because the top-3 ranks are mathematically locked, there are 0 early-rank regressions; 232 queries show positive metric gains, 95 queries are ties, and only 18 queries exhibit minor displacement confined to ranks $\ge 4$.

### 4.2 CAND-CASCADE vs. CAND-F
- The recovery over Candidate F is $+0.0567$ MRR (+42.41% relative gain).
- On a query-paired basis, the Wilcoxon test is decisively significant ($p = 1.09 \times 10^{-14}$).
- However, the repository-clustered bootstrap 95% CI is $[-0.0079, +0.1033]$, which crosses zero.
- **Root Cause**: Candidate F's collapse was concentrated in large, symbol-dense repositories with extensive utility networks (`etcd-io/etcd`, `huggingface/transformers`, `vitejs/vite`). In smaller repositories with $\le 2$ queries and sparse call graphs, Candidate F did not experience severe hub dilution. When small repositories are oversampled in the cluster bootstrap, the variance increases.

### 4.3 CAND-CASCADE vs. BASE-REPOMAP
- Pinned RepoMap maintains an advantage in aggregate MRR ($-0.0387$, $p = 9.03 \times 10^{-4}$).
- However, as demonstrated in the task breakdown, `CAND-CASCADE` directly outperforms RepoMap on `comment2context` ($0.1699 > 0.1590$) and `edit2ripple` ($0.2532 > 0.2344$), as well as across the entire Go repository track ($0.2910 > 0.2850$) and JavaScript track ($0.0363 > 0.0314$).
- RepoMap's macro lead stems primarily from `code2test` ($0.2284$ vs. $0.0969$), where RepoMap benefits from its fine-grained tree-sitter method call tree.

---

## 5. Excluded Observations & Data Integrity Ledger

- **Total Queries in Benchmark Population**: 345
- **Queries Evaluated**: 345
- **Queries Excluded**: 0 (100.0% coverage across all 25 repositories)
- **Total Tall Rows**: 2,415 ($345 \text{ queries} \times 7 \text{ configurations}$)
- **Missing or Dropped Values**: 0
- **Random Seed Recorded**: `42`
- **Bootstrap Iterations**: `10,000`
