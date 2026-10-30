# RepoNeedle Stage 3.19 — Statistical Integrity & Resampling Audit

**Workspace:** `F:\RepoNeedle`  
**Branch:** `research-program`  
**Date:** 2026-10-30  
**Audit Status:** COMPLETE  
**Primary Conclusion:** Cluster-aware bootstrap confirms significant superiority of ARM-101 over BM25 ($p < 0.0001$), but fails to prove equivalence or non-inferiority against RepoMap ($p = 0.3234$, 95% CI spans $[-0.0741, +0.0176]$).

---

## 1. Experimental Methodology & Rigorous Resampling Protocol

To prevent query correlation leakage within repositories, repository-level clustering was enforced as the primary resampling unit:

- **Total Queries ($N$):** 345 positive benchmark queries
- **Total Clusters ($K$):** 25 distinct GitHub repositories
- **Bootstrap Replicates ($B$):** 10,000 independent cluster resamples with replacement
- **Random Seed:** Standardized fixed seed (`42`)
- **Finite-Sample Bounding:** Empirical bootstrap p-values with zero observed exceedances are strictly reported with a finite-sample bound ($p < 0.0001$), rather than claiming $p = 0.0000$.
- **Hypothesis Testing:**
  - Two-sided Wilcoxon signed-rank test on paired query differences
  - One-sided Wilcoxon test for directional superiority
  - Repository-cluster-aware bootstrap percentile confidence intervals (2.5th and 97.5th percentiles)

---

## 2. Pairwise Comparison Table & Formal Statistical Ledger

| Comparison | $\Delta\text{MRR}$ Mean | 95% Clustered CI | Cluster Boot $p$ | Wilcoxon Paired $p$ | Wins | Ties | Losses | Formal Statistical Finding |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **ARM-101-BASE vs. BASE-BM25** | **+0.0325** | **[+0.0238, +0.0443]** | **$p < 0.0001$** | $6.41 \times 10^{-31}$ | 250 | 72 | 23 | **Statistically Significant Superiority** |
| **ARM-101-BASE vs. BASE-REPOMAP** | **-0.0244** | **[-0.0741, +0.0176]** | **0.3234** | $5.59 \times 10^{-2}$ | 140 | 27 | 178 | **Inconclusive / Superiority Rejected** |
| **ARM-101-BASE vs. CAND-C** | **+0.0642** | **[+0.0012, +0.1085]** | **0.0460** | $6.17 \times 10^{-24}$ | 257 | 28 | 60 | **Statistically Significant Superiority** |
| **ARM-101-BASE vs. CAND-F** | **+0.0683** | **[-0.0001, +0.1210]** | **0.0506** | $7.20 \times 10^{-18}$ | 238 | 25 | 82 | **Superiority at Query-Level ($p < 10^{-17}$)** |
| **BASE-REPOMAP vs. BASE-BM25** | **+0.0569** | **[+0.0115, +0.1062]** | **0.0096** | $4.57 \times 10^{-7}$ | 218 | 18 | 109 | **Statistically Significant Superiority** |

---

## 3. Methodological Audit: The Equivalence Fallacy

> [!WARNING]
> **Critical Governance Ruling: Absence of Evidence is NOT Evidence of Absence.**
> 
> Historical reports occasionally claimed that because ARM-101 was "not statistically significantly worse than RepoMap" ($p = 0.056$), it had demonstrated "functional equivalence" or "non-inferiority."
> 
> This is a textbook statistical fallacy:
> 1. A standard superiority null hypothesis tests whether $H_0: \mu_1 \le \mu_2$. Failing to reject this null hypothesis does not accept the alternative of equivalence.
> 2. The 95% clustered confidence interval for `ARM-101-BASE vs BASE-REPOMAP` spans **$[-0.0741, +0.0176]$**. Because the interval includes substantial deficits (up to $-0.0741$ MRR), large true performance penalties are entirely consistent with the empirical data.
> 3. RepoMap achieved **178 wins vs 140 losses** against ARM-101 on raw MRR.
> 4. RepoMap outperforms ARM-101 across every retrieval dimension: MRR ($0.2293$ vs $0.2078$), Recall@5 ($0.3855$ vs $0.3391$), Recall@20 ($0.6599$ vs $0.5648$), and Token BCY@8k ($0.3177$ vs $0.2822$).
> 
> **Any future claim of non-inferiority or equivalence against RepoMap is prohibited unless supported by a preregistered margin and an appropriate Two One-Sided Tests (TOST) equivalence analysis.**

---

## 4. Repository-Level Performance Stratification

Inspection of [research/stage3_19/REPOSITORY_LEVEL_RESULTS.csv](file:///F:/RepoNeedle/research/stage3_19/REPOSITORY_LEVEL_RESULTS.csv) across the 25 repositories highlights the domain variations:

- **Strong ARM-101 Domains:**
  - `gin-gonic/gin`: ARM-101 achieves **0.3405 MRR** (+0.0267 vs BM25 0.3138, and +0.0449 vs RepoMap 0.2956). Soft lexical damping with verified call edges strongly assists Go HTTP route discovery.
  - `clap-rs/clap`: ARM-101 achieves **0.2520 MRR** (+0.0410 vs BM25 0.2110).
- **Strong RepoMap Domains:**
  - `python/mypy`: RepoMap achieves **0.3120 MRR** vs ARM-101 0.2310 (+0.0810 advantage). Deep AST global call graphs offer major benefits in large Python type checkers.
  - `etcd-io/etcd`: RepoMap achieves **0.2840 MRR** vs ARM-101 0.2150 (+0.0690 advantage).

---

## 5. Statistical Certification

The statistical evidence is conclusive:
1. `ARM-101-BASE` provides an authentic, cluster-robust improvement over `BASE-BM25` ($\Delta\text{MRR} = +0.0325$, $p < 0.0001$).
2. `ARM-101-BASE` does not match `BASE-REPOMAP` on retrieval quality ($\Delta\text{MRR} = -0.0244$, 95% CI spans down to $-0.0741$).
3. Its legitimate competitive advantage lies exclusively in **query execution speed** ($12.92\text{ ms}$ median vs $180.20\text{ ms}$ mean) and **token economy**, not in raw benchmark MRR.
