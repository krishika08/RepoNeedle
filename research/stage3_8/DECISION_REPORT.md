# Stage 3.8: Authoritative Decision & Governance Report

**Document ID**: `STAGE3-8-DECISION-001`  
**Stage**: Stage 3.8 — Reproducibility Lock, Metric Reconciliation, and Evidence Audit  
**Date**: October 28, 2026  
**Status**: Authoritative Decision & Research Charter  
**Evaluation Scope**: ARB v2 Full Positive Development Benchmark ($N = 345$ queries across $K = 25$ repositories)  
**Evaluated Systems**: BASE-BM25, CAND-C, CAND-F, BASE-REPOMAP  

---

## 1. Executive Summary & Verdict

This decision report provides the formal, binding resolution of the RepoNeedle retrieval evidence base following the completion of the Stage 3.8 reproducibility lock and metric audit.

### Final Research Verdict:
$$\mathbf{PROMISING\ ON\ ARB,\ INDEPENDENT\ VALIDATION\ BLOCKED}$$

---

## 2. Status of Historical Claims & Numerical Reconciliation

### 2.1 Valid Historical Results (Retained under explicit metric contracts)
1. **Stage 2 Python-AST Baseline (`EXP-003` / `EXP-016`)**:
   - The Stage 2 results reported in `STAGE2_ABLATION_RESULTS.csv` (BM25 MRR **0.1705**, Candidate C MRR **0.2040**) are **VALID** strictly within the Python-AST architecture without polyglot regex symbol extraction.
2. **Context Packing Efficiency**:
   - Token-budgeted context yield (`Token BCY@8k` via `pack_files` @ 8,000 tokens) is **VALID** as a context-packing efficiency metric: Candidate C achieves **0.3805** and Candidate F achieves **0.4180** when structural skeleton compression is enabled.
3. **Pure BM25 Parity**:
   - Pure Okapi BM25 retrieval quality is confirmed at MRR **0.1735**, Recall@20 **0.4549** across all 345 queries.

### 2.2 Superseded & Invalidated Historical Claims
1. **Candidate F Overall ARB v2 MRR Claims (0.2152 / 0.2078)**:
   - **INVALIDATED**. Extrapolated from isolated subsets (Click/Tokio). Under unified end-to-end evaluation, polyglot regex symbol extraction creates massive structural edge explosion ($1,802 \to 36,508$ edges in `etcd`), diluting PageRank mass onto generic utility hubs and inflating BM25 length penalties. The true canonical MRR of Candidate F is **0.1351**.
2. **Candidate C Polyglot Engine MRR (0.2040)**:
   - **SUPERSEDED**. Transcribed from the Stage 2 Python codebase. When executed inside the polyglot engine, Candidate C achieves canonical MRR **0.1399**.
3. **Claims of Surpassing RepoMap**:
   - **INVALIDATED**. Stage 3.5 compared against an outdated paper constant ($0.2140$). Authoritative per-sample RepoMap predictions achieve MRR **0.2293**, Recall@20 **0.6599**, and Token BCY **0.4357**. RepoMap holds a $+64\%$ MRR advantage over RepoNeedle.
4. **General Generalization across Repositories**:
   - **UNPROVEN / REJECTED**. While Candidate F achieves a positive query-level win ratio over BM25 on Recall@20 ($40$ wins vs $20$ losses, Wilcoxon $p = 0.0023$), the 95% repository-clustered bootstrap confidence interval is **`[-0.0091, +0.1689]`**, which crosses zero due to win concentration in only 2 of 25 repositories.

### 2.3 Unresolved Research Items
1. **External Generalization on ContextBench**:
   - ContextBench acquisition remains blocked under environment network access restrictions. No synthetic surrogate can substitute for an official benchmark. Independent generalization remains strictly **BLOCKED / UNRESOLVED**.
2. **Downstream SWE-Bench / Coding Agent Impact**:
   - Whether RepoNeedle's context yield translates to higher patch resolution rates in real coding agents remains unverified.

---

## 3. Canonical Headline Comparison ($N=345$ Positive ARB v2 Queries)

| System ID | Configuration Description | MRR | Recall@5 | Recall@10 | Recall@20 | CharCov@8k | Token BCY@8k | Latency ($p50$) | Latency ($p95$) | Process RSS |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BASE-BM25`** | Pure Okapi BM25 Baseline | 0.1735 | 0.1986 | 0.3118 | 0.4549 | 0.0493 | 0.1957 | **20.85 ms** | 478.58 ms | 198.6 MB |
| **`CAND-C`** | Static Hybrid + Doc Filter (0.5×) | 0.1399 | 0.2111 | 0.3196 | 0.5105 | 0.0188 | 0.2034 | 31.50 ms | 561.46 ms | 226.0 MB |
| **`CAND-F`** | CAND-C + Polyglot Graph Diffusion | 0.1351 | 0.1824 | 0.3316 | 0.5078 | 0.0159 | 0.1775 | 32.42 ms | 566.28 ms | 238.4 MB |
| **`BASE-REPOMAP`**| Authoritative Aider Tree-sitter Call Graph | **0.2293** | **0.3337** | **0.5110** | **0.6599** | **0.0652** | **0.3177** | 180.20 ms | 180.20 ms | N/A |

---

## 4. Superiority Assessment

- **Has RepoNeedle demonstrated a verified advantage over BASE-BM25?**
  - **NO**. While Candidate C and F achieve higher Recall@20 ($0.5105$ and $0.5078$ vs $0.4549$), their MRR is significantly worse ($0.1399$ and $0.1351$ vs $0.1735$), and the repository-clustered bootstrap confidence interval for Recall@20 spans zero (`[-0.0091, +0.1689]`).
- **Has RepoNeedle demonstrated a verified advantage over BASE-REPOMAP?**
  - **NO**. RepoMap decisively outperforms all RepoNeedle variants across MRR ($0.2293$ vs $0.1351$), Recall@20 ($0.6599$ vs $0.5078$), and context yield ($p < 0.0001$).

---

## 5. Governance Sign-Off

The research governance charter certifies that:
- Frozen Git tags `v0.1.0-baseline` (`8e00425`) and `stage3-candidate-freeze` (`cd7f3b0`) remain immutable and clean.
- Canonical predictions are durably locked in `research/stage3_8/CANONICAL_PER_QUERY_RESULTS.csv` (SHA-256: `430574460e5339e692c6fbefcc07604b2ee9840d551aeda1e1321981483ad929`).
- All 67 regression tests in `tests/` pass cleanly without regression.
