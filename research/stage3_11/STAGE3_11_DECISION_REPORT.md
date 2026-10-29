# RepoNeedle Stage 3.11: Decision Report — Function-Level Graph Retrieval Research

**Stage**: Stage 3.11 — Function-Level Graph Retrieval Research  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Anchor Commit**: `768f69d`  
**Date**: October 29, 2026  
**Official Gate Verdict**: **`FAIL — PRIMARY PREREGISTERED CRITERION NOT MET (KEEP DEFAULT UNCHANGED)`**  

---

## 1. Executive Summary

Stage 3.11 evaluated whether constructing a fine-grained, language-aware function-level call graph could improve retrieval quality over `CONTROL-CASCADE` across all 345 positive ARB v2 queries under the strict canonical evaluation contract.

The primary preregistered candidate, **`FUNCTION-GRAPH`** (integrating Level 1 verified and Level 2 structural call edges with the Rank 1–3 lexical freeze), achieved:
- **MRR**: **$0.1901$** vs. **$0.1882$** for `CONTROL-CASCADE` (delta **$+0.001892$**, **$+1.00\%$ relative improvement**).
- **Statistical Significance**: Statistically significant over `CONTROL-CASCADE` ($p = 0.00101$ raw, $p = 0.00486$ Holm-adjusted, repository-clustered 95% CI $[+0.000052, +0.003216]$).
- **Fractional Recall@20**: **$0.5605$** vs. **$0.5503$** ($+0.0102$, non-inferior).
- **Latency**: **$16.11\text{ ms}$** median warm query latency.

**However, the primary candidate failed Preregistered Criterion 1**: it achieved a **$+1.00\%$ relative MRR gain**, falling short of the mandatory **$+2.0\%$ relative improvement threshold** ($\text{MRR} \ge 0.1920$). Furthermore, compared to `TEST-GRAPH` ($0.1897$ MRR), the gain was statistically indistinguishable ($p = 0.761$, clustered 95% CI $[-0.000403, +0.000960]$).

In strict accordance with scientific integrity and the preregistered research protocol:
- **The default production retrieval configuration remains UNCHANGED** (retaining `CONTROL-CASCADE`).
- No claims of benchmark superiority or production readiness are made.
- ARB v2 results are maintained strictly as developmental/regression metrics; independent generalization on ContextBench remains **`BLOCKED / PRELIMINARY`**.

---

## 2. Audit of Pre-Registered Acceptance Criteria

| Criterion | Requirement | Observed Outcome | Gate Status |
| :--- | :--- | :--- | :---: |
| **1. Relative MRR Improvement** | $\ge +2.0\%$ relative gain over `CONTROL-CASCADE` ($\text{MRR} \ge 0.1920$) | $+1.00\%$ relative gain ($\text{MRR} = 0.1901$) | **FAIL** |
| **2. Clustered Uncertainty** | 95% repository-clustered bootstrap CI excludes zero | Clustered 95% CI: $[+0.000052, +0.003216]$ | **PASS** |
| **3. Recall Non-Inferiority** | Fractional Recall@20 degradation $\le 0.5\text{ pp}$ ($\Delta \ge -0.0050$) | $\text{Recall@20} = 0.5605$ vs $0.5503$ ($\Delta = +0.0102$) | **PASS** |
| **4. Repository Diversity** | Benefit distributed across multiple repositories | Gains observed across 14 of 25 repositories | **PASS** |
| **5. Protocol Compliance** | 100% unconstrained candidate pool, zero query-time leakage | 100% unconstrained pool, zero leakage, distinct budgets | **PASS** |
| **6. Resource Bounds** | Median latency $< 25\text{ ms}$, memory scalable | Median latency $16.11\text{ ms}$, RSS $935.7\text{ MB}$ across full test run | **PASS** |
| **7. Test Suite & Integrity** | All unit/regression tests pass deterministically | 158 tests passing across test suite | **PASS** |

**Final Determination**: Because Criterion 1 was not satisfied, `FUNCTION-GRAPH` is **NOT promoted to default**.

---

## 3. Exploratory Discovery: The Lexical Freeze Paradox

Stage 3.11 preregistered an exploratory ablation variant, **`FUNCTION-GRAPH-NO-FREEZE`**, to test Secondary Hypothesis H3 (whether the Rank 1–3 BM25 freeze was essential to protect early precision).

The empirical outcome decisively rejected H3:
- **MRR**: **$0.2082$** ($\Delta = +0.019998$, **$+10.6\%$ relative improvement** over `CONTROL-CASCADE`).
- **Wins vs. Losses**: **139 wins**, **23 losses**, 183 ties (**$6.04 : 1$ win-to-loss ratio**).
- **Active Queries**: 162 queries active (up from 62 under the freeze).
- **Statistical Significance**: $p = 1.01 \times 10^{-17}$ (Holm-adjusted $p < 0.00001$).
- **Clustered 95% CI**: $[+0.011679, +0.029519]$ (lower bound exceeds $+1.1$ percentage points).
- **Recall@20**: **$0.5648$** (highest of any RepoNeedle configuration to date).

### Explanation of Mechanism
In earlier stages (3.6–3.9), the Rank 1–3 freeze was mandatory because file-level heuristic graphs were noisy and caused severe rank displacement. However, with the high-precision function-level call graph engineered in Stage 3.11 (702,501 verified edges, $92.2\%$ precision), the freeze transformed from a protective shield into an **artificial ceiling**:
- When BM25 ranked a gold target at rank 4, 5, or 6 with undeniable verified call evidence connecting it to rank 1, the frozen ranker was forbidden from promoting it into ranks 1–3.
- Removing the freeze allowed genuine function-level dependencies to promote gold files directly to rank 1, generating an $8\times$ larger MRR improvement.

Because `FUNCTION-GRAPH-NO-FREEZE` was preregistered as an exploratory variant rather than the primary candidate, scientific integrity requires that we **do not retroactively promote it in Stage 3.11**. Instead, it forms the foundation for Stage 3.12.

---

## 4. Benchmark Stance on Official RepoMap

- **Quality**: Official `BASE-REPOMAP` (commit `9e4d689`) remains decisively superior to all RepoNeedle variants on retrieval quality ($0.2293$ MRR and $0.6599$ Recall@20 vs. $0.1901$ MRR and $0.5605$ Recall@20). RepoNeedle does **not** outperform RepoMap on quality.
- **Latency**: RepoNeedle maintains an order-of-magnitude execution efficiency advantage:
  - `FUNCTION-GRAPH`: **$16.11\text{ ms}$** median warm query latency
  - `BASE-REPOMAP`: **$180.20\text{ ms}$** median warm query latency (**$11.2\times$ slower**)

---

## 5. Independent Validation Status

Independent validation on official **ContextBench** remains **`BLOCKED / PRELIMINARY`** due to external sandbox network isolation preventing automated download from Hugging Face (`Contextbench/ContextBench`). All evaluations in this report are conducted on ARB v2 as a development/regression benchmark and are not claimed as independent generalization.

---

## 6. Recommendations for Stage 3.12

1. **Preregister Soft Lexical Damping**: Formally preregister a controlled, non-rigid ranker that replaces the binary Rank 1–3 freeze with a continuous lexical confidence penalty (e.g. dynamic margin gating where graph boost must exceed a calibrated threshold to displace a rank 1 BM25 hit).
2. **In-Degree Hub Attenuation**: Implement inverse logarithmic fan-in attenuation ($\frac{1}{\log(1 + \text{deg}_{\text{in}})}$) to eliminate the 11 utility-sink regressions identified in [`FAILURE_ANALYSIS.md`](file:///F:/RepoNeedle/research/stage3_11/FAILURE_ANALYSIS.md).
3. **Adopt Verified-Only Default**: Preregister `FUNCTION-GRAPH-VERIFIED` as the base edge set, excluding unverified Level 2 structural method edges.
