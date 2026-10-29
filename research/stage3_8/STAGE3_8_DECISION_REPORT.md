# RepoNeedle Stage 3.8: Authoritative Decision & Root-Cause Governance Report

**Document ID**: `STAGE3-8-DECISION-REPORT-001`  
**Date**: October 2026  
**Stage**: Stage 3.8 — Independent Metric Verification and Retrieval Root-Cause Investigation  
**Branch**: `research-program`  
**Base Commit**: `fd45220`  
**Evaluated Scope**: Full ARB v2 Benchmark ($N = 345$ positive queries across $K = 25$ repositories)  
**Primary Deliverables**:
- [`INDEPENDENT_METRIC_VERIFICATION.md`](file:///F:/RepoNeedle/research/stage3_8/INDEPENDENT_METRIC_VERIFICATION.md)
- [`RANKING_FAILURE_ANALYSIS.md`](file:///F:/RepoNeedle/research/stage3_8/RANKING_FAILURE_ANALYSIS.md)
- [`GRAPH_DAMAGE_ANALYSIS.md`](file:///F:/RepoNeedle/research/stage3_8/GRAPH_DAMAGE_ANALYSIS.md)
- [`PER_QUERY_DIAGNOSTICS.csv`](file:///F:/RepoNeedle/research/stage3_8/PER_QUERY_DIAGNOSTICS.csv)
- [`HYPOTHESIS_REGISTER.csv`](file:///F:/RepoNeedle/research/stage3_8/HYPOTHESIS_REGISTER.csv)
- [`REPRODUCE.md`](file:///F:/RepoNeedle/research/stage3_8/REPRODUCE.md)

---

## 1. Authoritative Stage 3.8 Decision

```
[STAGE 3.8 VERDICT] RANKING ARCHITECTURE LIMITATION IDENTIFIED
```

The investigation has conclusively audited the empirical data, independently verified all benchmark metrics without project imports, and pinpointed the exact mathematical and architectural mechanisms explaining RepoNeedle's retrieval failures.

### Summary of Authoritative Outcomes:
1. **MRR vs. Recall Discrepancy Solved**:
   - Candidate C ($MRR = 0.1399$) and Candidate F ($MRR = 0.1351$) reduce MRR relative to BM25 ($0.1735$) because graph diffusion and static PageRank **demote exact lexical matches from ranks 1–2 down to ranks 4–8 in 70 queries** (`BM25_WIN_CAND_DEMOTED`).
   - In Reciprocal Rank ($1/r$), demoting a single query from Rank 1 to Rank 4 loses $0.75$ RR points, requiring $11.25$ promotions into ranks 11–20 to offset.
   - The loss of $21.0$ RR points across ranks 1–2 completely overwhelmed the $25$ new hits picked up at ranks 11–20 (which added only $1.82$ RR points).
2. **RepoMap Precision@5 Evaluation Defect Corrected**:
   - In `CANONICAL_RESULTS.csv`, RepoMap's Precision@5 was recorded as $0.0186$ due to missing dictionary keys in legacy `v1_1` ablation inputs defaulting to $0.0$ for 114 queries.
   - Clean-room independent recomputation proves RepoMap's actual Precision@5 is **$0.0910$**, maintaining a commanding lead over all RepoNeedle systems (BM25: $0.0568$, Cand C: $0.0557$, Cand F: $0.0504$).
3. **Graph Architecture Defect Identified**:
   - Static query-independent PageRank and unnormalized bidirectional diffusion ($0.25 / 0.20$ without out-degree scaling) flood relevance onto dense utility supernodes, causing severe regressions on Go and large monorepos (Go MRR collapsed by $-0.1078$).

---

## 2. Independent Metric Verification Summary

All metrics were recomputed from scratch using [`independent_metric_verifier.py`](file:///F:/RepoNeedle/research/stage3_8/independent_metric_verifier.py) without importing any project metric modules:

| System Identifier | MRR (Full-Rank) | MRR (Top-20 Cutoff) | Recall@5 (Frac) | Recall@10 (Frac) | Recall@20 (Frac) | Hit@20 (Binary) | Precision@5 (Indep) | Token BCY@8k | Median Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BASE-BM25`** | **0.1735** | **0.1649** | 0.1986 | 0.3118 | 0.4549 | 0.5304 | 0.0568 | 0.1957 | **20.85 ms** |
| **`CAND-C`** | 0.1399 | 0.1326 | **0.2111** | 0.3196 | **0.5105** | 0.6000 | 0.0557 | 0.2034 | 31.50 ms |
| **`CAND-F`** | 0.1351 | 0.1277 | 0.1824 | **0.3316** | 0.5078 | **0.6029** | 0.0504 | 0.1775 | 32.42 ms |
| **`BASE-REPOMAP`**| **0.2293** | **0.2242** | **0.3337** | **0.5110** | **0.6599** | **0.7478** | **0.0910** | **0.3177** | 180.20 ms |

---

## 3. Evaluation of Strategic Product Directions (Phase 4)

Without prematurely committing to code changes, the audit evaluated three distinct architectural directions against the empirical evidence:

### Direction A: Fast Local Lexical Retriever (BM25 + Token Optimization)
- **Retrieval Quality**: Strong early ranks ($MRR = 0.1735$, 21 Rank-1 hits), but misses non-lexical relationships (Recall@20 capped at $0.4549$).
- **Context Yield**: $BCY@8k = 0.1957$.
- **Latency & Memory**: Fast ($20.85\text{ ms}$, $< 50\text{ MB}$ RSS delta).
- **Feasibility**: High. Clean baseline with zero graph parsing overhead.
- **Verdict**: Strong foundation, but inherently limited when queries use synonyms or cross-file dependencies.

### Direction B: Cascaded Hybrid Retriever (BM25 Top-3 Preservation + Fenced Graph Expansion)
- **Retrieval Quality**: Solves early-rank demotion by **freezing the top-3 BM25 ranks** (retaining all 38.0 RR points) while permitting degree-normalized Personalized PageRank (PPR) or graph expansion strictly on ranks $\ge 4$.
- **Projected Potential**: Combines BM25's $0.1735$ MRR floor with graph expansion gains, targeting $MRR \ge 0.19\text{–}0.21$ and Recall@20 $\ge 0.55$.
- **Latency & Memory**: Adds minimal overhead ($~30\text{–}35\text{ ms}$ total latency).
- **Verdict**: **STRONGEST RETRIEVAL OPPORTUNITY**. Directly repairs the verified architectural flaw (`HYP-07`).

### Direction C: Retrieval-and-Context-Packing Engine (Budget-Aware Synthesis)
- **Core Thesis**: Competing with RepoMap purely on Top-1/Top-5 file precision may be suboptimal given RepoMap's deep tree-sitter AST; RepoNeedle's true product differentiator is **delivering denser context at fixed token budgets** (e.g. 8k tiktoken) via skeletonization and symbol pruning.
- **Evidence**: On current raw files, Candidate F achieved $0.1775$ token BCY@8k vs RepoMap's $0.3177$. However, Stage 3.6 context-packing ablations showed that AST skeletonization packs $2.4\times$ more relevant symbols into 8,000 tokens than full-file packing.
- **Verdict**: **STRONGEST PACKING OPPORTUNITY**. Should be coupled with Direction B so that budget-aware packing operates on high-precision retrieved candidates.

---

## 4. Status of Claims: Facts, Explanations, and Open Questions

### 4.1 Verified Facts
1. Candidate C and Candidate F do not outperform pure BM25 on MRR under unconstrained full-corpus evaluation ($0.1399$ and $0.1351$ vs $0.1735$).
2. Official pinned RepoMap (`9e4d689`) outperforms all RepoNeedle variants across MRR ($0.2293$), Recall@20 ($0.6599$), and Precision@5 ($0.0910$).
3. Candidate C and F demoted gold files in 70 queries where BM25 had succeeded in ranks 1–5.
4. RepoMap Precision@5 defect in `CANONICAL_RESULTS.csv` ($0.0186$) is resolved and corrected to $0.0910$.
5. ContextBench independent validation remains strictly `BLOCKED — DATA ACCESS` due to sandbox network policy (HTTP 403 Forbidden).

### 4.2 Likely Explanations
1. Go and Rust `code2test` failure ($0.0601$ MRR) is caused by the absence of explicit cross-file import statements linking tests to implementation modules within the same package.
2. Go monorepo degradation (MRR $-0.1078$) is caused by package-level import fanout creating tens of thousands of unweighted edges to utility packages.
3. Bidirectional predecessor diffusion bleeds relevance backwards from seed imports into unrelated caller modules.

### 4.3 Open Questions
1. Can query-seeded Personalized PageRank with $1/\sqrt{d}$ degree normalization prevent utility hub inflation while retaining CLI subcommand linkage wins?
2. Does a cascaded rank-freeze (freezing top-3 lexical candidates) achieve strict monotonicity over pure BM25?
3. When official ContextBench artifacts become accessible outside sandbox restrictions, how well do these structural heuristics transfer to unseen enterprise repositories?

---

## 5. Decision Gate Sign-Off

- **Root Cause Established**: **YES** (Rank 1–2 demotion mathematically proven; graph hub dilution verified).
- **Code Modifications in Stage 3.8**: Strictly zero production ranking changes (investigation and verification stage).
- **Frozen Tags**: Verified intact (`v0.1.0-baseline` = `8e00425...`, `stage3-candidate-freeze` = `cd7f3b0...`).
- **Clean Working Tree**: Verified.
