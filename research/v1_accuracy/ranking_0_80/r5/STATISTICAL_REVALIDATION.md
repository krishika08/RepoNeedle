# RepoNeedle — Phase R5: Statistical Revalidation and Sensitivity Audit

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R5 — Function-Level, Change-Aware Code Retrieval  
**Date**: November 2, 2026  
**Status**: Formal Statistical Inference & Sensitivity Report  

---

## 1. Executive Summary & Audit Reproduction

All metrics for **Baseline Treatment A (R2 Baseline)** and **Treatment F (Change-Impact Retrieval)** were reproduced directly from the 345 per-query records in [`PER_QUERY_COMPARISON.jsonl`](file:///F:/RepoNeedle/research/v1_accuracy/ranking_0_80/r5/PER_QUERY_COMPARISON.jsonl):

| Split | Queries | Repos | Baseline A (MRR) | Treatment F (MRR) | Observed Delta ($\Delta$) | Baseline Hit@1 | Treatment F Hit@1 | Hit@1 Delta |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Validation** | 60 | 5 | 0.2971 | **0.3235** | **+0.0264** | 16.67% | **20.00%** | +3.33% |
| **Held-Out** | 75 | 5 | 0.2965 | **0.3183** | **+0.0218** | 17.33% | **18.67%** | +1.34% |
| **Train** | 210 | 15 | 0.4544 | **0.4799** | **+0.0256** | 25.71% | **29.52%** | +3.81% |
| **Overall** | 345 | 25 | 0.3927 | **0.4176** | **+0.0249** | 22.32% | **25.51%** | +3.19% |

*Audit Verdict: All reported figures reproduced bit-for-bit with zero discrepancies.*

---

## 2. Repository-Clustered Bootstrap Analysis ($B=10,000$)

Because queries originating from the same repository share common languages and structural conventions, queries within a repository are correlated. We resample entire repository clusters with replacement:

| Partition | Repositories ($K$) | Queries ($N$) | Observed $\Delta$ | 95% Clustered CI | Clustered $P^*(\Delta^* \le 0)$ | Statistical Verdict at $\alpha = 0.05$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Validation** | 5 | 60 | **+0.0264** | **`[+0.0040, +0.1250]`** | **0.0007** | **STATISTICALLY SIGNIFICANT** |
| **Held-Out** | 5 | 75 | **+0.0218** | `[-0.0088, +0.0637]` | 0.0843 | **NOT STATISTICALLY SIGNIFICANT** |
| **Train** | 15 | 210 | **+0.0256** | `[-0.0012, +0.0521]` | 0.0328 | **BORDERLINE SIGNIFICANT** |
| **Overall** | 25 | 345 | **+0.0249** | **`[+0.0097, +0.0424]`** | **0.0009** | **STATISTICALLY SIGNIFICANT** |

### Critical Auditor Mandate:
> [!IMPORTANT]
> **GOVERNANCE RULE ENFORCEMENT**:  
> While the **Overall** 95% clustered confidence interval is strictly positive (`[+0.0097, +0.0424]`, $p = 0.0009$), **this cannot be used as substitute evidence for held-out significance**.
> 
> On the **Held-Out partition alone ($K=5$)**, the 95% clustered confidence interval spans zero (`[-0.0088, +0.0637]`, $p = 0.0843$). While the empirical delta is positive ($\Delta = +0.0218$), with only 5 repository clusters, the variance remains too wide to claim statistical significance at $\alpha = 0.05$.

---

## 3. Per-Repository Improvement and Regression Breakdown

Evaluating all 25 repositories individually:

| Repository Name | Split | Queries | Baseline MRR | Treatment F MRR | Delta | Audit Classification |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `etcd-io/etcd` | Train | 41 | 0.4190 | **0.4960** | **+0.0770** | IMPROVED |
| `gin-gonic/gin` | Train | 88 | 0.5405 | **0.5620** | **+0.0216** | IMPROVED |
| `clap-rs/clap` | Train | 10 | 0.3666 | **0.3777** | **+0.0111** | IMPROVED |
| `tox-dev/tox` | Train | 2 | 0.2622 | **0.5179** | **+0.2557** | IMPROVED |
| `tokio-rs/tokio` | Val | 38 | 0.4059 | **0.4317** | **+0.0258** | IMPROVED |
| `huggingface/diffusers` | Val | 16 | 0.1082 | **0.1147** | **+0.0065** | IMPROVED |
| `pydantic/pydantic` | Val | 1 | 0.5000 | **1.0000** | **+0.5000** | IMPROVED |
| `pytest-dev/pytest` | Held | 7 | 0.3937 | **0.4874** | **+0.0937** | IMPROVED |
| `vitejs/vite` | Held | 25 | 0.1580 | **0.2074** | **+0.0493** | IMPROVED |
| `pallets/click` | Train | 26 | 0.3939 | 0.3939 | +0.0000 | TIED |
| `caddyserver/caddy` | Train | 13 | 0.4311 | 0.4339 | +0.0028 | TIED |
| `spring-projects/spring-boot`| Train | 8 | 0.4203 | 0.4169 | -0.0034 | TIED |
| `scrapy/scrapy` | Train | 3 | 0.3454 | 0.3449 | -0.0005 | TIED |
| `fastapi/fastapi` | Train | 3 | 0.2095 | 0.2093 | -0.0003 | TIED |
| `ipython/ipython` | Train | 2 | 0.2917 | 0.2917 | +0.0000 | TIED |
| `numpy/numpy` | Train | 1 | 0.5000 | 0.5000 | +0.0000 | TIED |
| `mockito/mockito` | Train | 1 | 0.0303 | 0.0303 | +0.0000 | TIED |
| `HypothesisWorks/hypothesis` | Train | 1 | 1.0000 | 1.0000 | +0.0000 | TIED |
| `microsoft/playwright` | Val | 4 | 0.0421 | 0.0421 | +0.0000 | TIED |
| `eslint/eslint` | Val | 1 | 0.0051 | 0.0052 | +0.0001 | TIED |
| `huggingface/transformers` | Held | 36 | 0.4032 | 0.4012 | -0.0020 | TIED |
| `python/mypy` | Held | 1 | 0.2000 | 0.2000 | +0.0000 | TIED |
| `astral-sh/ruff` | Held | 6 | 0.1357 | **0.1049** | **-0.0309** | **REGRESSED** |
| `pypa/pip` | Train | 5 | 0.4682 | **0.4321** | **-0.0361** | **REGRESSED** |
| `vuejs/core` | Train | 6 | 0.1936 | **0.1709** | **-0.0227** | **REGRESSED** |

**Summary**: 9 Repositories Improved, 13 Repositories Tied, 3 Repositories Regressed.

---

## 4. Per-Task Improvement Breakdown

| Task Track | Query Count | Baseline A (MRR) | Treatment F (MRR) | Delta ($\Delta$) | Relative Gain | Primary Winning Mechanism |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `code2test` | 106 | 0.4130 | **0.4504** | **+0.0374** | **+9.05%** | `TESTS_BEHAVIOR` edge activation |
| `edit2ripple` | 58 | 0.3395 | **0.3766** | **+0.0371** | **+10.92%** | `IMPORTS_DEPENDENCY` traversal |
| `comment2context`| 80 | 0.3038 | **0.3347** | **+0.0309** | **+10.17%** | Subword token stem matching |
| `trace2code` | 101 | 0.4724 | 0.4724 | +0.0000 | +0.00% | Neutral (SFS already optimal) |

---

## 5. Leave-One-Repository-Out Sensitivity (Jackknife Analysis)

To ensure the observed improvements are not driven by a single dominant repository, we compute the treatment delta when omitting each repository:

### 5.1 Validation Jackknife ($K=5$)
- Baseline Validation Delta: **+0.0264**
  - Omit `eslint/eslint`: Delta = **+0.0268**
  - Omit `huggingface/diffusers`: Delta = **+0.0336**
  - Omit `microsoft/playwright`: Delta = **+0.0283**
  - Omit `pydantic/pydantic`: Delta = **+0.0184**
  - Omit `tokio-rs/tokio`: Delta = **+0.0275**
- **Verdict**: The validation gain is robust and invariant across all 4-repository subsets.

### 5.2 Held-Out Jackknife ($K=5$)
- Baseline Held-Out Delta: **+0.0218**
  - Omit `astral-sh/ruff`: Delta = **+0.0264**
  - Omit `huggingface/transformers`: Delta = **+0.0437**
  - Omit `pytest-dev/pytest`: Delta = **+0.0144**
  - Omit `python/mypy`: Delta = **+0.0221**
  - Omit `vitejs/vite`: Delta = **+0.0080**
- **Verdict**: The held-out delta remains positive under every single omitted repository.

