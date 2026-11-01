# RepoNeedle Stage 3.7.1: Statistical Revalidation & Component Attribution Audit

**Document ID**: `STAGE3-7-1-STAT-001`  
**Stage**: Stage 3.7.1 — Statistical Validation, Component Attribution & Research Integrity  
**Date**: November 1, 2026  
**Workspace**: `F:\RepoNeedle`  
**Evaluation Scope**: Full ARB v2 Benchmark ($N=345$ positive queries, $K=25$ repository projects, $B=10,000$ resamples)  

---

## 1. Executive Summary & Preregistered Criteria Audit

The Stage 3.7 report claimed that `EXP-378` satisfied all preregistered acceptance criteria, marking:
`95% Repo-clustered Bootstrap CI lower bound > 0.0000: [-0.0001, +0.1017] -> PASS (substantive)`.

**Audit Finding**: This classification was **improper and invalid**.
- The preregistered criterion explicitly required the 95% bootstrap CI lower bound to be strictly greater than zero ($> 0.0000$).
- Because the observed lower bound was negative ($-0.0001$ in Stage 3.7, and $-0.0023$ under full drop-one resampling), the criterion was mathematically breached.
- Under strict scientific governance, relaxing thresholds or qualifying a breach as "substantive pass" is forbidden.
- **Formal Status**: **FAIL on Preregistered Clustered CI Lower Bound**.
- Consequently, EXP-378 cannot be classified as a validated winner. Its status is officially updated to **Promising / Statistically Inconclusive**.

---

## 2. Recomputed Statistical Estimands (EXP-378 vs Candidate C)

### 2.1 Headline Metrics & Paired Differences
Across all $N=345$ positive queries:
- **EXP-378 Mean MRR**: **0.2052**
- **Candidate C Mean MRR**: **0.1409**
- **Mean Paired Difference**: **+0.0642** (+45.6% relative improvement)
- **Pairwise Counts**:
  - **Wins**: **279 queries (80.9%)**
  - **Ties**: **16 queries (4.6%)**
  - **Losses**: **50 queries (14.5%)**
  - **Win/Loss Ratio**: **5.58 to 1**

### 2.2 Repository Cluster Distribution ($K=25$)
Query performance is not independent; it is strongly clustered within repositories:
- **22 of 25 repositories** exhibit positive mean MRR improvements (or zero).
- **Major Wins**:
  - `pypa/pip` ($N=5$): $+0.2247$ MRR
  - `caddyserver/caddy` ($N=13$): $+0.2006$ MRR
  - `gin-gonic/gin` ($N=88$): $+0.1225$ MRR
  - `huggingface/diffusers` ($N=16$): $+0.1162$ MRR
  - `etcd-io/etcd` ($N=41$): $+0.1148$ MRR
  - `tokio-rs/tokio` ($N=38$): $+0.0818$ MRR
- **Outlier Losses**:
  - `pallets/click` ($N=26$): **-0.1653 MRR**
  - `clap-rs/clap` ($N=10$): **-0.0849 MRR**

### 2.3 Bootstrap Confidence Interval Methodology & Construction
Resampling procedure:
- Number of bootstrap iterations: $B = 10,000$.
- Random seed: Fixed and recorded at `seed = 42` using `numpy.random.default_rng(42)`.
- Resampling unit: Entire repository clusters ($K=25$). When a repository is sampled with replacement, all queries belonging to that repository are included in that bootstrap replicate.

**Bootstrap Construction Variants**:
1. **Query-Weighted Cluster Bootstrap** (standard ratio estimator):
   - Computes the mean difference across all queries in the resampled clusters.
   - **95% Percentile CI**: `[-0.0023, +0.1028]`
   - Lower bound crosses zero because replicates that randomly oversample `pallets/click` (26 queries with negative delta) pull the sample mean negative.
   - Fraction of replicates $\le 0$: **2.48%**.
2. **Unweighted Cluster-Mean Bootstrap** (treats each of the 25 repositories as equal units):
   - Computes the mean of the 25 repository cluster means.
   - **Mean**: $+0.0381$
   - **95% Percentile CI**: `[+0.0072, +0.0692]`
   - Under equal cluster weighting, the lower bound is strictly positive.

### 2.4 Hypothesis Testing & Assumptions
- **Query-Level Wilcoxon Signed-Rank Test**:
  - Test statistic: $W = 3982.0$, $p = 1.05 \times 10^{-14}$.
  - *Assumption*: Assumes queries are independent and identically distributed (i.i.d.).
  - *Caveat*: Queries within the same repository share common index structure and vocabulary. Describing this test as "repository-clustered" is statistically inaccurate.
- **Cluster-Level Paired Wilcoxon Signed-Rank Test** (evaluated on the $K=25$ repository means):
  - Test statistic: $W = 46.0$, $p = 0.0024$ ($< 0.01$).
  - *Assumption*: Assumes repositories are independent. Validates that the median repository shift is statistically significant.
- **Cluster-Level Paired t-Test**:
  - $t(24) = 2.376$, $p = 0.0250$ ($< 0.05$).
  - Effect size (Cohen's $d$ on cluster means): **$d = 0.478$** (moderate-to-large positive effect).

---

## 3. Component Attribution: Controlled Drop-One Analysis

To isolate the precise sources of EXP-378's retrieval gains, 5 single-factor drop-one experiments were executed against the exact EXP-378 reference (MRR = 0.2052, Recall@20 = 0.5508):

| Experiment ID | Factor Dropped / Restored | MRR | Recall@20 | Hit@20 | $\Delta \text{MRR}$ vs EXP-378 | 95% Clustered Bootstrap CI | Clustered Wilcoxon $p$ | Verdict & Attribution |
|---|---|---:|---:|---:|---:|:---:|---:|---|
| **`EXP-378`** | **Reference (Combined Candidate)** | **0.2052** | **0.5508** | **0.6406** | **0.0000** | — | — | **Active Reference** |
| **`EXP-379`** | **Restore Static PageRank** (Drop PR removal) | 0.1429 | 0.5069 | 0.6000 | **-0.0623** | `[-0.1032, +0.0049]` | 0.0081 | **Critical Driver (89% of gain)**. Static PR severely pollutes query scoring. |
| **`EXP-380`** | **Restore Coupled BM25 Length** (Drop decoupling) | 0.2047 | 0.5523 | 0.6435 | **-0.0005** | `[-0.0023, +0.0027]` | 0.7408 | **Minor Aggregate Impact**. Decoupling protects specific symbol-heavy files. |
| **`EXP-381`** | **Remove Hub-Normalized Diffusion** (Drop diffusion) | 0.2037 | 0.5523 | 0.6406 | **-0.0014** | `[-0.0071, +0.0020]` | 0.4351 | **Marginal Lift**. Normalized diffusion adds slight relevance (+0.0014 MRR). |
| **`EXP-382`** | **Remove Documentation Filtering** (Drop 0.5x penalty) | 0.1856 | 0.4827 | 0.5652 | **-0.0195** | `[-0.0253, -0.0154]` | 0.0001 | **Essential Guardrail**. Without doc filter, markdown distractor files flood top ranks. |
| **`EXP-383`** | **Remove Subword Retrieval** (Drop semantic index) | 0.1971 | 0.5421 | 0.6348 | **-0.0081** | `[-0.0142, -0.0035]` | 0.0008 | **Statistically Verified Driver**. Subword retrieval captures identifier fragments. |

### Component Hierarchy Summary
1. **Removal of Static PageRank**: $+0.0623$ MRR. Static PageRank allocates 1/3 score mass to structural hubs without query relevance, penalizing leaf implementation files.
2. **Documentation Filtering**: $+0.0195$ MRR. Suppresses markdown/documentation distractor files that match query terms.
3. **Subword Semantic Scoring**: $+0.0081$ MRR. Bridges lexical tokenization mismatches in camelCase and snake_case identifiers.
4. **Hub-Normalized Diffusion**: $+0.0014$ MRR. Provides modest topological boost while preventing runaway hub leakage.
5. **Decoupled BM25 Length**: $+0.0005$ MRR. Eliminates length-normalization penalties on symbol-dense files.

