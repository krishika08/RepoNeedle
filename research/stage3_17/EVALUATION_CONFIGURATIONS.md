# RepoNeedle Stage 3.17 — Frozen Evaluation Configurations & Candidate Reconciliation

**Document ID**: `STAGE3-17-CONFIG-001`  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `548dab5eea6c71c3e9982676289098d9e0dca5f0`  
**Production Code Reference**: `12142e8`  

---

## 1. Executive Summary

This document specifies the exact, frozen configurations registered for independent external evaluation against ContextBench, and records the formal candidate naming reconciliation separating the invalidated historical prototype (Candidate F) from the legitimate candidate champion (`ARM-101-BASE`).

Under Stage 3.17 research governance:
1. No production ranking parameters, graph weights, or retrieval algorithms have been modified.
2. Candidate configurations are strictly frozen to prevent post-hoc tuning or benchmark overfitting.
3. Candidate F is formally barred from being presented as a champion.

---

## 2. Frozen Evaluation Configurations

| System Identifier | Architecture Specification | Graph Parameters | ARB v2 Dev MRR | ARB v2 Dev Recall@20 | ARB v2 Dev BCY@8k | ARB v2 P50 Latency | Governance Role |
|---|---|---|---|---|---|---|---|
| **`ARM-101-BASE`** | Soft Lexical Damping ($\tau=0.25$) + Level 1 Verified Function Call Edges | Damping $\tau=0.25$, Depth=1, Verified call edges only, Hub attenuation=None | **0.2078** | **0.5648** | **0.2822** | **12.92 ms** | **Preregistered RepoNeedle Candidate Champion** |
| **`BASE-BM25`** | Decoupled Okapi BM25 length-normalized scoring ($k_1=1.5, b=0.75$) | None (Lexical only) | **0.1752** | **0.4535** | **0.2150** | **10.24 ms** | **Preregistered Lexical Baseline (Lower Bound)** |
| **`BASE-REPOMAP`** | Official Aider RepoMap reference (commit `9e4d689`) | Tree-sitter AST symbol tags + personalized PageRank | **0.2293** | **0.6599** | **0.3177** | **180.20 ms** | **Preregistered External Leader Reference (Upper Bound)** |

### 2.1 Configuration Details

#### 1. Candidate Champion: `ARM-101-BASE`
- **Retrieval Mechanism**: Two-phase cascaded retrieval. Initial candidate generation uses Okapi BM25 token-level scoring. Graph enhancement extracts Level 1 verified function call edges (`caller -> callee`).
- **Soft Lexical Damping**: Graph boost factors are damped using a sigmoid/exponential curve ($\tau = 0.25$), preventing disconnected or low-lexical graph neighbors from dominating the top-k rankings.
- **Hub Attenuation**: None (unattenuated call edges). Experiments in Stage 3.14 demonstrated that universal or language-aware hub attenuation did not statistically significantly improve MRR over unattenuated call edges on ARB v2.
- **Hardware Footprint**: Pure CPU-first, zero GPU required. P50 latency is $12.92\text{ ms}$, representing a $13.9\times$ speedup over RepoMap.

#### 2. Lexical Baseline: `BASE-BM25`
- **Retrieval Mechanism**: Pure Okapi BM25 token matching with length normalization.
- **Role**: Serves as the primary null hypothesis benchmark. Any proposed graph-assisted retrieval system must demonstrate a statistically significant improvement ($p < 0.05$) over `BASE-BM25` on both MRR and Recall@20 to justify the computational overhead of graph parsing.

#### 3. External Reference Leader: `BASE-REPOMAP`
- **Retrieval Mechanism**: Upstream Aider RepoMap implementation as verified in Stage 3.10 and Stage 3.13. Extracts tree-sitter tags, builds an identifier reference graph, and computes personalized PageRank seeded with query identifiers.
- **Role**: Serves as the external state-of-the-art reference. On ARB v2, RepoMap achieved an MRR of $0.2293$ vs $0.2078$ for `ARM-101-BASE` (paired Wilcoxon $p = 0.0559$, not statistically significant at $\alpha = 0.05$).

---

## 3. Formal Candidate Naming Reconciliation

### 3.1 The Historical Candidate F Discrepancy
In Stage 3.5, "Candidate F" was reported as achieving an MRR of **0.2152** and Recall@20 of **0.5652**, claiming parity with RepoMap (Reported MRR: 0.2140).

However, forensic audits conducted in Stage 3.10, Stage 3.12A, and Stage 3.15 uncovered material evaluation flaws:
1. **Artificial Candidate Filtering**: The Stage 3.5 Candidate F evaluation did not evaluate against the full repository file corpus. Instead, it restricted candidate pools to a pre-filtered set of 20 files per task (heavily biased toward test directories for `code2test` tasks).
2. **Diagnostic Shortcuts**: Scoring routines took shortcuts in parsing and path matching that were not available in general retrieval.
3. **True Performance Collapse**: When Candidate F was re-evaluated under canonical, unconstrained full-repository retrieval across all 345 positive ARB v2 queries (Stage 3.14 & Stage 3.15), its true MRR collapsed to **0.1351**:
   - Candidate F Unconstrained MRR: **0.1351**
   - BM25 Baseline MRR: **0.1752**
   - Difference: **-0.0401** ($p = 0.0122$, Wilcoxon signed-rank test).
   - Candidate F was statistically significantly *worse* than standard BM25 lexical search when evaluated fairly.

### 3.2 Candidate Resolution Policy
To maintain rigorous scientific integrity:
1. **Candidate F is Formally Invalidated**: Candidate F is permanently retired as a flawed prototype. It must never be referred to as a "champion" or evaluated as a primary candidate.
2. **ARM-101 is the Legitimate Champion**: `ARM-101-BASE` was engineered with proper full-repository candidate generation, verified call edges, and soft lexical damping. It achieves **0.2078 MRR** ($+0.0326$ over BM25, $p < 0.001$) under strictly unconstrained, canonical evaluation conditions.
3. **No Retrospective Relabeling**: Historical records of Candidate F's collapse are preserved in Git history and audit reports (`research/stage3_15/RECONCILIATION_REPORT.md`) for complete provenance.

---

## 4. Frozen Acceptance Criteria for Independent Validation

When evaluated on the official ContextBench dataset (`default` 1,136 tasks and `contextbench_verified` 500 tasks), `ARM-101-BASE` must satisfy:

1. **Retrieval Quality**:
   - $\text{MRR}(\text{ARM-101}) > \text{MRR}(\text{BASE-BM25})$ with repository-clustered bootstrap $p < 0.05$.
   - $\text{Recall@20}(\text{ARM-101}) > \text{Recall@20}(\text{BASE-BM25})$ with repository-clustered bootstrap $p < 0.05$.
   - Parity with `BASE-REPOMAP`: Difference in MRR is either non-inferior or bounded within acceptable delta ($\Delta \text{MRR} > -0.03$).

2. **Query Latency**:
   - P50 query latency $< 20.0\text{ ms}$ on pure CPU.
   - P95 query latency $< 100.0\text{ ms}$.

3. **Memory Footprint**:
   - Process RSS $< 200.0\text{ MB}$ across all 66 benchmark repositories.

4. **Research Integrity**:
   - Zero target leakage enforced via [`LeakageGuard`](file:///F:/RepoNeedle/research/contextbench_evaluation/leakage_guard.py).
   - Strict denominator preservation: repository checkout failures or query exceptions recorded as score 0.0, never pruned.
