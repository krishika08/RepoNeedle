# REPONEEDLE STAGE 3.3: STATISTICAL ANALYSIS AND BUDGET BEHAVIOR REPORT

**Document ID**: `STAGE3.3-STAT-001`  
**Date**: 2026-10-28  
**Scope**: Paired Hypothesis Testing, 10,000 Bootstrap Confidence Intervals, and Empirical Budget Saturation Analysis  

---

## 1. Primary Statistical Comparisons on Held-Out Repositories ($N=14$)

### 1.1 Candidate C vs Pure BM25 Baseline
- **Observed Mean File Recall**: Candidate C = **0.9286**, Pure BM25 = **0.8929**
- **Observed Mean Block Recall**: Candidate C = **0.9286**, Pure BM25 = **0.9286**
- **Mean Paired Difference (\Delta_{\text{Recall}})**: **+0.0357**
- **Relative Gain**: **+4.00%**
- **Win / Tie / Loss Breakdown**: **1 Win, 13 Ties, 0 Losses**
  - Only 1 task (`facebook/react`) differed: Candidate C retrieved both required hook files, while BM25 retrieved only 1.
  - On the remaining 13 repositories, both systems achieved identical Recall (1.00 on 12 repos, 0.00 on `ripgrep`).
- **Paired $t$-test**: $t = 1.000$, $p = 0.3356$ (not statistically significant at \alpha = 0.05).
- **10,000 Clustered Bootstrap Confidence Interval**: **[0.0000, +0.1071]**
  - **Literal Rule 1 Check**: The lower bound is exactly **0.0000** (not strictly $> 0$). Rule 1 **FAILS**.
  - **Literal Rule 2 Check**: The relative gain of +4.00% is below the preregistered minimum threshold of +5.00%. Rule 2 **FAILS**.

### 1.2 Candidate C vs RepoMap Baseline
- **Observed Mean File Recall**: Candidate C = **0.9286**, RepoMap = **1.0000**
- **Observed Mean Block Recall**: Candidate C = **0.9286**, RepoMap = **1.0000**
- **Mean Paired Difference (\Delta_{\text{Recall}})**: **-0.0714**
- **Relative Difference**: **-7.14%**
- **Win / Tie / Loss Breakdown**: **0 Wins, 13 Ties, 1 Loss**
  - On `BurntSushi/ripgrep`, RepoMap captured the target printer crate via static call graph hierarchy, whereas Candidate C achieved 0.0 recall.
- **Paired $t$-test**: $t = -1.000$, $p = 0.3356$.
- **10,000 Clustered Bootstrap Confidence Interval**: **[-0.2143, 0.0000]**.
- **Separate Retrieval Ranking Precision**:
  - Candidate C achieved **0.9286 MRR** vs RepoMap's **0.6071 MRR** (+52.9% relative ranking advantage).
  - While RepoMap generates a wide structural survey, RepoNeedle places the primary culprit file at Rank 1 in 92.9% of queries.

---

## 2. Empirical Validation of Budget-Selection Mechanisms Under Saturated Budgets

The 19-task micro-benchmark was inherently incapable of exercising budget management features because total repository sizes ($<450$ tokens) were far below the 8,000-token prompt budget ($450 \ll 8000$).

To evaluate context-budget behavior under genuine pressure, Candidate systems were evaluated on a full saturated repository snapshot (`pallets/click`, 133 files, 108,257 tokens, $13.5\times$ over budget):

| System Configuration | Total Files Packed | Full Files | Skeleton Files | Doc Distractor Files | Tokens Used | Recall@8k | Precision@8k | Key Mechanistic Finding |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **BASE-BM25** | 10 | 10 | 0 | 6 | 7,977 | 0.0000 | 0.0000 | Budget exhausted by documentation; gold files crowded out. |
| **CAND-A (Full Files Only)** | 9 | 9 | 0 | 7 | 7,970 | 0.0000 | 0.0000 | Suffers severe doc crowding without distractor filter or skeletons. |
| **CAND-B (Candidate A + Skeletons)** | 11 | 6 | 5 | 5 | 7,971 | **0.5000** | 0.0909 | **Skeletons enable gold file entry**: Compressing 5 files allows `formatting.py` into the budget! |
| **CAND-C (B + Doc Filter 0.5x)** | 8 | 7 | 1 | **2** | 7,970 | **0.5000** | **0.1250** | **Doc distractors cut by 60%** (5 $	o$ 2), elevating core implementation files. |
| **CAND-E (D + Polyglot Symbols)** | 6 | 5 | 1 | **0** | 7,978 | **0.5000** | **0.1667** | **Zero doc distractors**, precision jumps from 0.00 to 0.1667. |

### Key Mechanistic Conclusions:
1. **Skeleton Compression Works**: When a repository exceeds the prompt budget, AST skeletons compress large, low-relevance files to their interface signatures, freeing up thousands of tokens for actual fix targets.
2. **Documentation Filtering Works**: Multiplying doc path scores by 0.5x effectively suppresses tutorial and markdown sprawl, preventing peripheral files from evicting core source modules.
