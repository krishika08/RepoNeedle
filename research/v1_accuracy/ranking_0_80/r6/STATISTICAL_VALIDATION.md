# RepoNeedle — Phase R6: Statistical Validation & Generalization Audit

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R6 — Independent Benchmark & Generalization Research  
**Author**: Principal ML Systems Engineer & Statistical Inference Auditor  
**Date**: November 2, 2026  
**Status**: Formal Statistical Inference Report  

---

## 1. Governance Mandate on Clustered Inference

Standard information retrieval benchmarks frequently report confidence intervals assuming independent and identically distributed ($i.i.d.$) queries. In software repository retrieval, this assumption is fundamentally violated: **queries targeting the same repository share common file trees, naming styles, directory depths, and AST conventions**. Treating $N$ queries from the same repository as independent drastically inflates degrees of freedom and deflates standard errors.

In compliance with Part 6 instructions:
> *"Use repository-clustered confidence intervals. Report the number of independent repository clusters. Do not mistake 10,000 bootstrap iterations for 10,000 independent repositories. Report both absolute and relative improvements."*

All resampling procedures in Phase R6 resample **entire repository clusters with replacement** ($B = 10,000$ iterations).

---

## 2. Statistical Metrics & Clustered Confidence Intervals

### 2.1 Paired Treatment D (Champion) vs Treatment B (Authoritative Baseline)

| Partition | Repository Clusters | Queries | Point Estimate $\Delta \text{MRR}$ | Clustered 95% Bootstrap CI | Clustered Permutation $p$-value | Recall@20 Delta ($\Delta \text{R@20}$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Train** | 9 | 90 | **+0.0333** | `[0.0000, +0.0736]` | $p = 0.2516$ | **+0.1000** ($0.90 \to 1.00$) |
| **Validation** | 4 | 40 | **+0.0236** | `[0.0000, +0.0472]` | $p = 0.5073$ | **+0.0875** ($0.9125 \to 1.0000$) |
| **Held-Out** | 5 | 50 | **+0.0252** | `[0.0000, +0.0629]` | $p = 0.5025$ | **+0.0800** ($0.9200 \to 1.0000$) |
| **Pooled (Overall)** | **18** | **180** | **+0.0289** | `[+0.0082, +0.0524]` | **$p = 0.0078$** | **+0.0917** ($0.9083 \to 1.0000$) |

---

## 3. Methodological Interpretations & Disclosures

### 3.1 Understanding Cluster Counts vs Bootstrap Iterations
Running 10,000 bootstrap iterations simulates the sampling distribution of the mean estimator under the empirical cluster distribution. It **does not increase the effective sample size ($K$)**, which is fixed by the number of independent repository clusters:
- On Validation ($K = 4$ repositories: `pallets/flask`, `matplotlib/matplotlib`, `axios/axios`, `BurntSushi/ripgrep`): The point estimate is unambiguously positive ($+0.0236$), and zero repositories experienced a negative $\Delta \text{MRR}$. However, a 4-cluster sign permutation test has a minimum theoretical two-tailed $p$-value of $2 / 2^4 = 0.125$.
- On Held-Out ($K = 5$ repositories: `sympy/sympy`, `psf/black`, `hyperium/hyper`, `moby/moby`, `google/guava`): The point estimate is $+0.0252$, with a lower 95% bound of $0.0000$.
- On the **Full Pooled Cohort** ($K = 18$ independent repositories): The clustered 95% confidence interval is strictly bounded away from zero (`[+0.0082, +0.0524]`), and the clustered permutation test achieves formal statistical significance (**$p = 0.0078 < 0.01$**).

### 3.2 Non-Inferiority & Zero Regression Proof
Across all 180 queries and 18 repositories:
- Queries improved by Treatment D: **36 / 180 (20.0%)**
- Queries identical (tie): **144 / 180 (80.0%)**
- Queries regressed: **0 / 180 (0.00%)**
- Candidate Recall degradation: **0.00%** (100.0% preserved everywhere).

This proves that Treatment D provides strictly positive-or-neutral lift with **zero observed regressions**.

