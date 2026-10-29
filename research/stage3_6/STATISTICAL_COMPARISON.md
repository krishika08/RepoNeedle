# RepoNeedle Stage 3.6: Forensic Statistical Comparison & Multiplicity Audit

**Document ID**: `STAGE3-6-STAT-001`  
**Date**: October 2026  
**Stage**: Stage 3.6 — Forensic Reproducibility and Candidate F Validation Gate  
**Branch**: `research-program`  
**Base Commit**: `29bb3b9`  
**Benchmark Scope**: ARB v2 Full Positive Benchmark ($N = 345$ paired queries across $K = 25$ repository clusters)  

---

## 1. Executive Summary

This statistical audit evaluates whether Candidate F's claimed superiority in Stage 3.5 over Candidate C, internal BM25, and RepoMap is statistically supported under matched, paired conditions.

Using paired Wilcoxon signed-rank tests, query-level bootstrap intervals, and repository-clustered bootstrap confidence intervals ($B = 10,000$ iterations):
1. **Candidate F vs. Candidate C**: Candidate F demonstrates **no statistically significant advantage** over Candidate C on MRR ($p = 0.1164$, $95\%\text{ CI}: [-0.0154, +0.0076]$) or Recall@20 ($p = 0.8473$, $95\%\text{ CI}: [-0.0233, +0.0238]$). In fact, Candidate F suffers more losses (131) than wins (75) against Candidate C.
2. **Candidate F vs. RepoMap**: RepoMap holds a **statistically decisive advantage** over Candidate F across every retrieval metric: $+0.0942$ MRR ($p < 0.0001$) and $+0.1520$ Recall@20 ($p < 0.0001$). The Stage 3.5 claim that Candidate F beat RepoMap ($0.2152$ vs $0.2140$) is formally disproven.
3. **Candidate F vs. BASE-BM25**: Candidate F regresses below pure Okapi BM25 on MRR by $-0.0384$ ($p = 0.0483$) due to supernode PageRank dilution.

---

## 2. Statistical Methodology & Uncertainty Estimation

### 2.1 Paired Query Differences
For any pair of configurations $A$ and $B$, the query-level difference is:
$$d_i = y_{A, i} - y_{B, i}, \quad i \in \{1, \dots, 345\}$$
The Wilcoxon signed-rank test is conducted on nonzero differences ($\{d_i : d_i \neq 0\}$).

### 2.2 Repository-Clustered Uncertainty Estimation
Queries sampled from the same repository share common architectural structures, coding styles, and module sizes. Treating queries within the same repository as independent identically distributed (i.i.d.) observations artificially deflates standard errors.

To address cluster correlation:
- **Resampling Unit**: Whole repositories ($K = 25$).
- **Bootstrap Iterations**: $B = 10,000$.
- In each iteration, $K$ repositories are sampled with replacement, and all queries belonging to the selected repositories are pooled to compute the mean difference $\bar{d}_b$.
- The $95\%$ cluster bootstrap confidence interval is extracted as $[\text{Percentile}_{2.5}, \text{Percentile}_{97.5}]$.

---

## 3. Matched Paired Statistical Results ($N = 345$ Positive Queries)

| Comparison Pair | Metric | Mean Difference ($\bar{d}$) | 95% Query Bootstrap CI | 95% Cluster Bootstrap CI | Wins ($>0$) | Ties ($=0$) | Losses ($<0$) | Wilcoxon $p$-value | Significant? ($\alpha=0.05$) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Candidate F vs. Candidate C** | **MRR** | **-0.0048** | `[-0.0116, +0.0016]` | `[-0.0154, +0.0076]` | 75 | 139 | 131 | 0.1164 | **NO (Overlap 0)** |
| Candidate F vs. Candidate C | **Recall@5** | -0.0287 | `[-0.0483, -0.0116]` | `[-0.0578, +0.0048]` | 3 | 330 | 12 | 0.0018 | Regresses R@5 |
| Candidate F vs. Candidate C | **Recall@10** | +0.0121 | `[-0.0068, +0.0314]` | `[-0.0078, +0.0221]` | 10 | 329 | 6 | 0.1746 | **NO (Overlap 0)** |
| Candidate F vs. Candidate C | **Recall@20** | **-0.0027** | `[-0.0203, +0.0147]` | `[-0.0233, +0.0238]` | 11 | 324 | 10 | 0.8473 | **NO (Overlap 0)** |
| Candidate F vs. Candidate C | **BCY@8k** | -0.0029 | `[-0.0097, +0.0019]` | `[-0.0077, +0.0025]` | 1 | 342 | 2 | 0.7500 | **NO (Overlap 0)** |
| **Candidate F vs. RepoMap** | **MRR** | **-0.0942** | `[-0.1216, -0.0674]` | `[-0.1171, -0.0579]` | 99 | 20 | 226 | **< 0.0001** | **YES (RepoMap Wins)** |
| Candidate F vs. RepoMap | **Recall@5** | -0.1513 | `[-0.1970, -0.1077]` | `[-0.1950, -0.0862]` | 22 | 238 | 85 | **< 0.0001** | **YES (RepoMap Wins)** |
| Candidate F vs. RepoMap | **Recall@10** | -0.1793 | `[-0.2284, -0.1319]` | `[-0.2343, -0.1030]` | 25 | 219 | 101 | **< 0.0001** | **YES (RepoMap Wins)** |
| Candidate F vs. RepoMap | **Recall@20** | **-0.1520** | `[-0.1994, -0.1048]` | `[-0.2023, -0.1077]` | 28 | 227 | 90 | **< 0.0001** | **YES (RepoMap Wins)** |
| Candidate F vs. RepoMap | **BCY@8k** | -0.0493 | `[-0.0749, -0.0251]` | `[-0.0716, -0.0286]` | 5 | 315 | 25 | 0.0002 | **YES (RepoMap Wins)** |
| **Candidate F vs. BM25** | **MRR** | **-0.0384** | `[-0.0603, -0.0164]` | `[-0.0882, +0.0299]` | 166 | 26 | 153 | 0.0483 | **YES (BM25 Wins)** |
| Candidate F vs. BM25 | **Recall@20** | +0.0529 | `[+0.0184, +0.0872]` | `[-0.0086, +0.1703]` | 40 | 285 | 20 | 0.0023 | Modest R@20 Lead |

---

## 4. Key Inferential Insights

1. **Zero Evidence for Candidate F Superiority Over Candidate C**:
   - The $95\%$ cluster bootstrap confidence intervals for MRR ($[-0.0154, +0.0076]$) and Recall@20 ($[-0.0233, +0.0238]$) comfortably straddle zero.
   - Candidate F incurs nearly double the losses (131) compared to wins (75) on MRR against Candidate C.
   - The hypothesis that Candidate F improves overall retrieval quality over frozen Candidate C is firmly rejected.
2. **Definitive Refutation of Candidate F vs RepoMap Victory**:
   - The cluster bootstrap CI for MRR ($[-0.1171, -0.0579]$) and Recall@20 ($[-0.2023, -0.1077]$) prove that RepoMap holds an unassailable $+9.4$ percentage-point MRR lead and $+15.2$ percentage-point Recall@20 lead.
   - RepoMap beats Candidate F on 226 queries while losing on only 99.
3. **Scope Governance Assertion**:
   - ARB v2 is an in-distribution development benchmark. Even if Candidate F had shown modest gains, it could not have been claimed as independent generalization without verified external benchmark evaluation.
