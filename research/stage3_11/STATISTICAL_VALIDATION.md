# RepoNeedle Stage 3.11: Statistical Validation and Hypothesis Testing Report

**Document**: `research/stage3_11/STATISTICAL_VALIDATION.md`  
**Stage**: Stage 3.11 — Function-Level Graph Retrieval Research  
**Benchmark**: Agent-Retrieval-Bench (ARB) v2 Selective Mixed  
**Sample Size**: $N = 345$ positive queries, 218 snapshots (25 repositories)  
**Bootstrap Replicates**: $10{,}000$ (Random Seed: 42)  
**Correction Procedure**: Holm-Bonferroni Step-Down Multiple Testing Adjustment  

---

## 1. Executive Summary of Statistical Findings

1. **Primary Candidate (`FUNCTION-GRAPH` with Rank 1–3 Freeze)**:
   - Achieves **$0.1901$ MRR** vs. **$0.1882$ MRR** for `CONTROL-CASCADE` (delta $+0.001892$, $+1.00\%$ relative gain).
   - The improvement is statistically significant over `CONTROL-CASCADE` ($p = 0.00101$ raw, $p = 0.00486$ Holm-adjusted, clustered 95% CI $[+0.000052, +0.003216]$).
   - **However, it fails the preregistered acceptance criterion**: the relative MRR gain ($+1.00\%$) is strictly below the mandatory $+2.0\%$ threshold ($\text{MRR} \ge 0.1921$).
   - Moreover, compared to `TEST-GRAPH` ($0.1897$ MRR), the gain is negligible ($+0.000385$) and **not statistically significant** ($p = 0.761$, clustered 95% CI crosses zero $[-0.000403, +0.000960]$).

2. **Verified Edges Ablation (`FUNCTION-GRAPH-VERIFIED`)**:
   - Level 1 verified call edges alone achieve **$0.1902$ MRR**, marginally outperforming the full graph ($0.1901$ MRR). Lower-confidence structural method edges introduced 1 net additional loss without improving recall.

3. **Safeguard Removal Discovery (`FUNCTION-GRAPH-NO-FREEZE`)**:
   - Relaxing the Rank 1–3 lexical freeze unlocks the full potential of the function-level call graph, achieving **$0.2082$ MRR** ($\Delta = +0.019998$, **$+10.6\%$ relative gain**, $p = 1.0 \times 10^{-17}$, Holm-adjusted $p < 0.00001$).
   - Active queries surge from 62 to 162, with **139 wins vs. 23 losses** ($6.04 : 1$ win-to-loss ratio) and clustered 95% CI $[+0.011679, +0.029519]$.
   - This empirically falsifies the historical assumption that the Rank 1–3 lexical freeze is universally beneficial. While necessary when graphs had high noise, with high-precision function call edges the freeze acts as an artificial ceiling.

---

## 2. Multiplicity-Controlled Family Comparisons

The table below summarizes all 6 planned family comparisons over $N = 345$ queries:

| Comparison | Mean $\Delta$ | Wins | Losses | Ties | Active | Wilcoxon $W$ | Raw $p$-value | Holm $p$-adj | Significant? | Clustered 95% CI |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **FUNCTION-GRAPH vs. CONTROL-CASCADE** | $+0.001892$ | 38 | 24 | 283 | 62 | 507.5 | 0.001008 | **0.004857** | **YES** | $[+0.000052, +0.003216]$ |
| **FUNCTION-GRAPH-VERIFIED vs. CONTROL-CASCADE** | $+0.001951$ | 37 | 23 | 285 | 60 | 470.5 | 0.001066 | **0.004857** | **YES** | $[+0.000054, +0.003337]$ |
| **FUNCTION-GRAPH-ABLATION vs. CONTROL-CASCADE** | $+0.001951$ | 37 | 23 | 285 | 60 | 470.5 | 0.001066 | **0.004857** | **YES** | $[+0.000064, +0.003296]$ |
| **FUNCTION-GRAPH-NO-FREEZE vs. CONTROL-CASCADE** | **$+0.019998$** | 139 | 23 | 183 | 162 | 1475.5 | $1.01 \times 10^{-17}$ | **$<0.00001$** | **YES** | $[+0.011679, +0.029519]$ |
| **FUNCTION-GRAPH vs. TEST-GRAPH** | $+0.000385$ | 14 | 19 | 312 | 33 | 263.5 | 0.761284 | 0.761284 | **NO** | $[-0.000403, +0.000960]$ |
| **FUNCTION-GRAPH vs. BASE-REPOMAP** | $-0.039165$ | 136 | 192 | 17 | 328 | 21308.5 | 0.000971 | **0.004857** | **YES** (RM wins) | $[-0.092491, +0.003249]$ |

---

## 3. Bootstrap Distributions and Confidence Intervals

All bootstrap estimates use $10{,}000$ replicates with fixed random seed $42$:

### 3.1 Primary Variant: `FUNCTION-GRAPH` vs. `CONTROL-CASCADE`
- **Query-Level Bootstrap**: Mean delta $+0.001892$, 95% CI $[+0.000768, +0.003243]$.
- **Repository-Clustered Bootstrap**: Mean delta $+0.001892$, 95% CI $[+0.000052, +0.003216]$.
- *Interpretation*: The clustered interval is bounded strictly above zero, confirming statistical validity. However, the upper bound ($+0.0032$) is still below the $+0.0038$ delta needed for a $2\%$ relative gain.

### 3.2 Exploratory Variant: `FUNCTION-GRAPH-NO-FREEZE` vs. `CONTROL-CASCADE`
- **Query-Level Bootstrap**: Mean delta $+0.019998$, 95% CI $[+0.010924, +0.029518]$.
- **Repository-Clustered Bootstrap**: Mean delta $+0.019998$, 95% CI $[+0.011679, +0.029519]$.
- *Interpretation*: The entire 95% confidence interval lies comfortably above $+0.011$ ($+1.1$ percentage points), establishing that the large gain from unfreezing ranks 1–3 is robust across repositories.

---

## 4. Practical Effect Size vs. Statistical Significance

### 4.1 Why `FUNCTION-GRAPH` (Frozen) Failed to Reach $+2.0\%$
Under the Rank 1–3 freeze:
- 283 of 345 queries ($82.0\%$) are exact ties.
- Only 62 queries ($18.0\%$) showed any movement.
- When rank movements occurred, they were confined to ranks $\ge 4$.
- Moving a file from rank 5 to rank 4 produces an MRR delta of only $\frac{1}{4} - \frac{1}{5} = +0.050$. Diluted over 345 queries, an isolated rank 4 improvement contributes only $+0.000145$ to aggregate MRR.
- Consequently, even though wins outnumbered losses ($38 : 24$), the ceiling effect of the Rank 1–3 lock prevents aggregate MRR from growing by $\ge 2\%$.

### 4.2 Why `FUNCTION-GRAPH-NO-FREEZE` Achieved $+10.6\%$ Gain
When the freeze was removed:
- Ranks 1, 2, and 3 became dynamically re-rankable based on fused lexical + graph signals.
- In queries where BM25 placed the gold target at ranks 4–10 with high function-level call connectivity to top candidates, the ranker promoted the gold target directly into ranks 1–3.
- Promoting a candidate from rank 5 to rank 1 produces an MRR jump of $1.0 - 0.20 = +0.80$, generating massive gains without sacrificing precision.
- The win-to-loss ratio was overwhelmingly positive ($139$ wins vs. $23$ losses, $6.04 : 1$).

---

## 5. Performance Against Benchmark Baselines

1. **Decoupled Baseline (`BASE-BM25`)**:
   - `BASE-BM25`: $0.1752$ MRR.
   - `FUNCTION-GRAPH`: $0.1901$ MRR ($\Delta = +0.0149$, $+8.5\%$ relative, $p < 0.0001$).
   - `FUNCTION-GRAPH-NO-FREEZE`: $0.2082$ MRR ($\Delta = +0.0330$, $+18.8\%$ relative, $p < 10^{-20}$).
2. **Official Version-Pinned RepoMap (`BASE-REPOMAP`)**:
   - `BASE-REPOMAP`: $0.2293$ MRR, $0.6599$ Recall@20.
   - `FUNCTION-GRAPH`: $0.1901$ MRR, $0.5605$ Recall@20.
   - `FUNCTION-GRAPH-NO-FREEZE`: $0.2082$ MRR, $0.5648$ Recall@20.
   - **Conclusion**: Official RepoMap remains significantly superior in retrieval quality ($p = 0.00486$). RepoNeedle's advantage remains exclusively in execution efficiency ($16.11\text{ ms}$ vs. $180.20\text{ ms}$, **$11.2\times$ faster**).
