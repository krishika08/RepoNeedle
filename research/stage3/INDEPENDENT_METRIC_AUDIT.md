# REPONEEDLE STAGE 3.1: INDEPENDENT METRIC AUDIT & EVIDENCE RECOMPUTATION

**Document ID**: `STAGE3.1-METRICS-001`  
**Audit Date**: 2026-10-28  
**Scope**: Literal Evaluation of Preregistered Rules on ContextBench Held-Out Test Partition ($N=14$)  

---

## 1. Executive Summary

This audit recomputes every retrieval and context metric directly from per-task predictions and applies the preregistered decision rules strictly to the held-out partition ($N=14$ tasks across 14 independent repositories).

### Core Audit Discoveries:
1. **Rule 1 (Bootstrap CI Lower Bound > 0) Fails**:
   - The 95% repository-clustered bootstrap confidence interval for $\Delta_{\text{Recall}}$ is **[0.0000, +0.1071]**.
   - The lower bound is exactly **0.0000**, NOT strictly greater than zero. Under literal pre-registered criteria, Rule 1 is **NOT SATISFIED**.
2. **Rule 2 (Minimum Meaningful Relative Gain $\ge 5.0\%$) Fails**:
   - The observed relative gain on Context Recall@8k is **+4.00%** (0.9286 vs 0.8929).
   - This falls below the preregistered threshold of $+5.0\%$. Under literal pre-registered criteria, Rule 2 is **NOT SATISFIED**.
3. **Statistical Sample Size is Underpowered ($N=14$)**:
   - Out of 14 tasks, RepoNeedle Candidate C produced **1 win, 13 ties, and 0 losses** against BM25.
   - Paired $t$-test: $t = 1.000$, $p = 0.3356$ (not statistically significant at $\alpha = 0.05$).
4. **RepoMap Outperforms RepoNeedle on Context Recall and F1**:
   - RepoMap achieved **1.0000 Context Recall@8k** and **0.8150 Context F1** vs RepoNeedle Candidate C **0.9286 Context Recall@8k** and **0.7435 Context F1**.
   - RepoNeedle beats RepoMap on file-level MRR (**0.9286 vs 0.6071**) because RepoMap prioritizes architectural centrality rather than term relevance.

---

## 2. Recomputed Aggregate Performance Table (Held-Out Partition, $N=14$)

| Metric | BASE-BM25 | BASE-REPOMAP | CAND-C (RepoNeedle Track A) | $\Delta$ (Cand C - BM25) | $\Delta$ (Cand C - RepoMap) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Context Recall@8k (Primary)** | 0.8929 | **1.0000** | 0.9286 | +0.0357 (+4.00%) | -0.0714 (-7.14%) |
| **Context Precision@8k** | 0.6881 | **0.7119** | 0.6405 | -0.0476 (-6.92%) | -0.0714 (-10.03%) |
| **Context F1** | 0.7483 | **0.8150** | 0.7435 | -0.0048 (-0.64%) | -0.0715 (-8.77%) |
| **Budgeted Context Yield (BCY@8k)** | 0.8939 | **1.0000** | 0.9286 | +0.0347 (+3.88%) | -0.0714 (-7.14%) |
| **Mean Reciprocal Rank (MRR)** | **0.9286** | 0.6071 | **0.9286** | +0.0000 (0.0%) | **+0.3214 (+52.9%)** |
| **Recall@20** | 0.9286 | **1.0000** | 0.9286 | +0.0000 (0.0%) | -0.0714 (-7.14%) |
| **Mean Query Latency** | 8.30 ms | **0.37 ms** | 3.23 ms | **-5.07 ms (2.6x faster)**| +2.86 ms |

---

## 3. Pairwise Per-Repository Breakdown Table ($N=14$)

| Repository | Language | BM25 Recall | RepoMap Recall | Cand C Recall | Win / Tie / Loss (vs BM25) | Win / Tie / Loss (vs RepoMap) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `django/django` | Python | 1.0000 | 1.0000 | 1.0000 | TIE | TIE |
| `sympy/sympy` | Python | 1.0000 | 1.0000 | 1.0000 | TIE | TIE |
| `scikit-learn/scikit-learn`| Python | 1.0000 | 1.0000 | 1.0000 | TIE | TIE |
| `astropy/astropy` | Python | 1.0000 | 1.0000 | 1.0000 | TIE | TIE |
| `matplotlib/matplotlib` | Python | 1.0000 | 1.0000 | 1.0000 | TIE | TIE |
| `sphinx-doc/sphinx` | Python | 1.0000 | 1.0000 | 1.0000 | TIE | TIE |
| `psf/requests` | Python | 1.0000 | 1.0000 | 1.0000 | TIE | TIE |
| `mwaskom/seaborn` | Python | 1.0000 | 1.0000 | 1.0000 | TIE | TIE |
| `pydata/xarray` | Python | 1.0000 | 1.0000 | 1.0000 | TIE | TIE |
| `pallets/flask` | Python | 1.0000 | 1.0000 | 1.0000 | TIE | TIE |
| `google/guava` | Java | 1.0000 | 1.0000 | 1.0000 | TIE | TIE |
| `facebook/react` | JavaScript | 0.5000 | 1.0000 | **1.0000** | **WIN (+0.5)** | TIE |
| `golang/go` | Go | 1.0000 | 1.0000 | 1.0000 | TIE | TIE |
| `BurntSushi/ripgrep` | Rust | 0.0000 | **1.0000** | 0.0000 | TIE | **LOSS (-1.0)** |

**Summary Accounting**:
- **Candidate C vs BM25**: **1 Win, 13 Ties, 0 Losses** (Dominant or equal on 14/14 repos, but only 1 distinguishing event).
- **Candidate C vs RepoMap**: **0 Wins, 13 Ties, 1 Loss** (RepoMap wins on `ripgrep` due to static call graph inclusion of printer crate).

---

## 4. Literal Application of Preregistered Decision Rules

| Preregistered Rule | Formally Registered Criterion | Observed Result | Literal Audit Verdict |
| :--- | :--- | :--- | :---: |
| **Rule 1: Clustered Bootstrap CI** | 95% Clustered Bootstrap CI lower bound $> 0$ | 95% CI is **[0.0000, +0.1071]**; lower bound $= 0$ | **FAIL (Not Strictly > 0)** |
| **Rule 2: Minimum Effect Size** | Relative gain on Context Recall $\ge +5.0\%$ | Relative gain is **+4.00%** | **FAIL (+4.0% < +5.0%)** |
| **Rule 3: Anti-Regression Boundary** | No individual repo regresses by $> -10.0\%$ vs BM25 | 0 losses vs BM25 (max regression is $0.0\%$) | **PASS** |
| **Rule 4: Latency & Efficiency** | Median latency $\le 50$ ms, Peak Memory $\le 100$ MB | Median latency = **3.23 ms**, Memory = **0.48 MB** | **PASS** |

### Methodological Rule on Replication Partition:
Preregistered scientific guidelines strictly prohibit using the overlapping replication partition ($N=5$) to compensate for a shortfall on the held-out partition ($N=14$). The held-out evidence must stand on its own merits.

**Overall Status**:
Because Rule 1 and Rule 2 were not met, full independent generalization cannot be claimed. The held-out evidence represents **PRELIMINARY GENERALIZATION EVIDENCE ONLY**.
