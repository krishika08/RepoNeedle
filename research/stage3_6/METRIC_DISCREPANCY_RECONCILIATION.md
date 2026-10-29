# RepoNeedle Stage 3.6: Forensic Reconciliation of Historical Metric Discrepancies

**Document ID**: `STAGE3-6-RECON-001`  
**Date**: October 2026  
**Stage**: Stage 3.6 — Forensic Reproducibility and Candidate F Validation Gate  
**Branch**: `research-program`  
**Base Commit**: `29bb3b9`  
**Target Historical Commit**: `4f78cc3` (Stage 3.5)  

---

## 1. Executive Summary

A critical objective of Stage 3.6 is to reconcile severe metric discrepancies between Stage 2, Stage 3.4, and Stage 3.5 deliverables. Specifically:
- **BM25 Recall@20**: Reported as `0.4467` in Stage 3.4, but jumped to `0.4928` in Stage 3.5 summary tables.
- **RepoMap Recall@20**: Reported as `0.6306` in Stage 3.4, but dropped to `0.5681` in Stage 3.5 summary tables.
- **Candidate C Recall@20**: Reported identically as `0.5516` across both reports.
- **RepoMap MRR**: Reported as a static constant `0.2140` across multiple documents.

Forensic code inspection reveals that **these discrepancies were caused by mixing two fundamentally incompatible metric definitions (Binary Hit@20 vs Multi-Target Fractional Recall), relying on candidate-restricted lookup dictionaries, and hardcoding static reference constants.**

---

## 2. Mathematical Root Cause: Binary Hit@K vs Multi-Target Fractional Recall

In information retrieval benchmarks where queries have multiple relevant targets ($|\text{gold}_i| \ge 1$), there are two distinct ways to define Recall@K:

### Definition A: Multi-Target Fractional Recall (Official ARB v2 Contract)
$$\text{Recall@K}_{\text{frac}} = \frac{1}{N} \sum_{i=1}^N \frac{|\text{gold}_i \cap \text{ranked}_{i, :K}|}{|\text{gold}_i|}$$
Each query receives a score in $[0.0, 1.0]$ proportional to the fraction of its relevant targets retrieved within the top $K$ ranks. If a query has 2 gold files and only 1 is retrieved, the score is $0.5$.

### Definition B: Binary Hit@K (Any-Target Hit Rate)
$$\text{Hit@K} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(|\text{gold}_i \cap \text{ranked}_{i, :K}| \ge 1)$$
Each query receives a binary score in $\{0.0, 1.0\}$. If at least one gold file is present in the top $K$, the score is $1.0$, completely ignoring whether other gold files were missed.

Because queries frequently possess multiple relevant files, $\text{Hit@K} \ge \text{Recall@K}_{\text{frac}}$ for all $K$.

---

## 3. Forensic Accounting of Each Metric Discrepancy

### 3.1 BM25 Recall@20 (`0.4467` vs `0.4928` vs Canonical `0.4549`)
- **Source of `0.4467`**: Stage 3.4 / Stage 2 evaluated BM25 using multi-target fractional recall on ARB v2 chunk subsets.
- **Source of `0.4928`**: In Stage 3.5 [`research/stage3_5/STAGE3_5_DECISION_REPORT.md`](file:///F:/RepoNeedle/research/stage3_5/STAGE3_5_DECISION_REPORT.md#L25), the authors evaluated $N=345$ positive queries. Exactly 170 queries had at least one gold hit in the top 20:
  $$\frac{170}{345} = 0.4927536\dots \approx \mathbf{0.4928}$$
  This was the **Binary Hit@20**, but was erroneously titled "Recall@20" in Table 1.2.
- **Canonical Result**: Under the official ARB v2 multi-target fractional recall contract evaluated on the full unconstrained repository corpus, BM25 Recall@20 is **0.4549** (or **0.4622** under canonical full-corpus formatting).
- **Comparability**: `0.4467` and `0.4928` cannot be directly compared because one is fractional recall and the other is binary hit rate.

### 3.2 RepoMap Recall@20 (`0.6306` vs `0.5681` vs Canonical `0.6599`)
- **Source of `0.6306`**: Stage 3.4 and [`research/stage3_5/evaluate_graph_retrieval.py:278`](file:///F:/RepoNeedle/research/stage3_5/evaluate_graph_retrieval.py#L278) cited `0.6306` as a static constant from an older v1.1 evaluation run under ARB chunk filtering.
- **Source of `0.5681`**: In Stage 3.5 [`research/stage3_5/STAGE3_5_DECISION_REPORT.md:30`](file:///F:/RepoNeedle/research/stage3_5/STAGE3_5_DECISION_REPORT.md#L30), RepoMap was evaluated on $N=345$ queries. Exactly 196 queries had at least one gold hit in the top 20:
  $$\frac{196}{345} = 0.5681159\dots \approx \mathbf{0.5681}$$
  Again, this was **Binary Hit@20**, but was mislabeled as "Recall@20".
- **Canonical Result**: Under the official ARB v2 fractional recall contract, version-pinned RepoMap (`9e4d689`) achieves **0.6599** Recall@20 across all 345 positive instances.
- **Comparability**: `0.6306` and `0.5681` cannot be compared due to the metric definition shift (fractional vs binary).

### 3.3 Candidate C Recall@20 (`0.5516` vs Canonical `0.5105`)
- **Source of `0.5516`**: In Stage 3.4, Candidate C was evaluated on candidate-restricted pools using pre-computed Stage 2 AST lookup dictionaries (`test_only` on `code2test`, `code_only` on `trace2code`), achieving fractional recall of `0.5516`.
- **The Stage 3.5 Distortion**: In Stage 3.5 Table 1.2, the authors copied Candidate C's fractional recall (`0.5516`) directly from Stage 3.4 and placed it side-by-side with RepoMap's binary Hit@20 (`0.5681`). Because binary hit rates are systematically higher than fractional recall, this created the illusion that Candidate C ($0.5516$) was within 1.6% of RepoMap ($0.5681$).
- **Canonical Result**: When Candidate C is evaluated end-to-end on the complete, unconstrained 25-repository corpus without candidate pre-filtering, its true fractional Recall@20 drops to **0.5105**.

### 3.4 RepoMap MRR (`0.2140` vs Canonical `0.2293`)
- **Source of `0.2140`**: In [`research/stage3_5/evaluate_graph_retrieval.py:278`](file:///F:/RepoNeedle/research/stage3_5/evaluate_graph_retrieval.py#L278), line 278 hardcoded:
  ```python
  repomap_all = {"mrr": 0.2140, "r5": 0.3185, "r10": 0.4786, "r20": 0.6306, "bcy8k": 0.3788, "lat": 180.20}
  ```
  This was an unmeasured paper reference constant from historical v1.1 evaluation.
- **Canonical Result**: Live empirical evaluation of version-pinned official RepoMap (`9e4d689`) establishes the true MRR as **0.2293**.

### 3.5 Candidate F MRR (`0.2152` vs Canonical `0.1351` / `0.1334`)
- **Source of `0.2152`**: Stage 3.5 computed Candidate F scores using synthetic 2-file fixtures containing hardcoded string bypasses (`"search.rs", "standard.rs"` and `core in my_crate and printer in o_crate`) and uncoupled Stage 2 lookup dictionaries.
- **Canonical Result**: Under true end-to-end full corpus execution with hardcoded bypasses excised, Candidate F achieves only **0.1351** (or **0.1334**) MRR due to supernode PageRank dilution.

---

## 4. Comprehensive Metric Reconciliation Table

| Metric / Configuration | Stage 3.4 Reported | Stage 3.5 Reported | True Canonical Reproduced | Exact Cause of Discrepancy | Comparability Status |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **`BASE-BM25` Recall@20** | 0.4467 | 0.4928 | **0.4549** (0.4622) | Stage 3.5 computed Binary Hit@20 ($170/345 = 0.4928$) and mislabeled as fractional recall. | `NON_COMPARABLE_METRIC_SHIFT` |
| **`BASE-REPOMAP` Recall@20** | 0.6306 | 0.5681 | **0.6599** | Stage 3.5 computed Binary Hit@20 ($196/345 = 0.5681$); Stage 3.4 cited older v1.1 chunk filter. Pinned RepoMap achieves 0.6599. | `NON_COMPARABLE_METRIC_SHIFT` |
| **`CAND-C` Recall@20** | 0.5516 | 0.5516 | **0.5105** | Stage 3.5 retained Stage 3.4 value evaluated on candidate-restricted pools rather than unconstrained full corpus. | `NON_COMPARABLE_POOL_SHIFT` |
| **`BASE-REPOMAP` MRR** | 0.2140 | 0.2140 | **0.2293** | Unmeasured static constant hardcoded in `evaluate_graph_retrieval.py:278`. Pinned RepoMap actually achieves 0.2293. | `SUPERSEDED_HARDCODED_CONSTANT` |
| **`CAND-F` MRR** | N/A | 0.2152 | **0.1351** (0.1334) | Evaluated on synthetic 2-file micro-fixtures with hardcoded bypasses. True full-corpus execution collapsed to 0.1351. | `FORMALLY_INVALIDATED` |
| **`CAND-F` Recall@20** | N/A | 0.5652 | **0.5078** | Stage 3.5 computed Binary Hit@20 ($195/345 = 0.5652$). True full-corpus fractional recall is 0.5078. | `FORMALLY_INVALIDATED` |
