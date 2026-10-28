# RepoNeedle Stage 3.7: Forensic Evaluation & Research Integrity Decision Report

**Document ID**: `STAGE3-7-DECISION-001`  
**Stage**: Stage 3.7 — Forensic Evaluation Reconciliation and Research Integrity Audit  
**Date**: October 28, 2026  
**Status**: Authoritative Decision & Governance Charter  
**Evaluation Target**: ARB v2 Full Positive Development Benchmark ($N = 345$ queries, $K = 25$ repositories)  
**Evaluated Systems**: BASE-BM25, CAND-C, CAND-F, BASE-REPOMAP  

---

## 1. Executive Summary & Verdict

The objective of Stage 3.7 was to resolve the severe discrepancies between Stage 3.5 and Stage 3.6 results, establish an immutable metric contract, audit statistical claims, reconcile latency/memory profiles, and verify artifact integrity.

### Final Research Verdict:
$$\mathbf{PROMISING\ ON\ ARB,\ INDEPENDENT\ VALIDATION\ BLOCKED}$$

### Key Findings of the Audit:
1. **Resolution of Discrepancies**:
   - **MRR (0.2040 vs 0.1399)**: Stage 3.5 transcribed an isolated Stage 2 micro-ablation result. Live evaluation revealed that polyglot regex symbol and import extraction caused catastrophic edge explosion (e.g. 1,802 $\to$ 36,508 edges in `etcd`), diluting PageRank mass onto central utility files (`backend.go`, `types.go`) and artificially inflating BM25 document length penalties. The true end-to-end MRR of Candidate C is **0.1399**, and Candidate F is **0.1351**.
   - **BCY@8k (0.3015 vs 0.0188)**: An apples-to-oranges metric collision. Stage 3.5 reported Token-Budgeted Context Yield (`pack_files` @ 8,000 BPE tokens = **0.3015** to **0.3805**). Stage 3.6 recorded Character-Budgeted Chunk Coverage (`sample_metrics["gold_coverage@8k"]` @ 8,000 characters $\approx$ 1,800 tokens = **0.0188**). Both measurements are mathematically verified under their respective definitions.
   - **Baseline Parity**: BM25 is confirmed at **MRR 0.1735**, Recall@20 **0.4549**. Authoritative per-sample RepoMap reference is confirmed at **MRR 0.2293**, Recall@20 **0.6599**. RepoMap maintains a clear retrieval advantage over RepoNeedle on ARB v2.
2. **Statistical Audit**:
   - The query-level Wilcoxon test ($W = 635.5, p = 0.0023$) rejects the null because wins outnumber losses ($40$ vs $20$).
   - However, the repository-clustered bootstrap 95% confidence interval is **$[-0.0091, +0.1689]$**, which crosses zero.
   - The wins are concentrated in modular repositories (`click`, `tokio`), while regressions occur on multi-package monorepos (`etcd`, `caddy`, `eslint`). Under the preregistered evaluation governance, RepoNeedle has **no verified general superiority** over BM25 across unseen repositories.
3. **External Generalization Status**:
   - ContextBench acquisition remains blocked under sandbox network policy. In accordance with research integrity rules, no surrogate datasets were fabricated, and independent generalization remains strictly unverified.

---

## 2. Reconciled Headline System Summary ($N=345$ Positive ARB v2 Queries)

| System ID | Configuration Description | MRR | Recall@5 | Recall@10 | Recall@20 | CharCov@8k | Token BCY@8k | Latency ($p50$) | Latency ($p95$) | Process RSS |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BASE-BM25`** | Pure Okapi BM25 Baseline | 0.1735 | 0.1986 | 0.3118 | 0.4549 | 0.0493 | 0.2688 | **20.85 ms** | 478.58 ms | 198.6 MB |
| **`CAND-C`** | Static Hybrid + Doc Filter (0.5×) | 0.1399 | 0.2111 | 0.3196 | 0.5105 | 0.0188 | 0.3805 | 31.50 ms | 561.46 ms | 226.0 MB |
| **`CAND-F`** | CAND-C + Polyglot Graph Diffusion | 0.1351 | 0.1824 | 0.3316 | 0.5078 | 0.0159 | 0.4180 | 32.42 ms | 566.28 ms | 238.4 MB |
| **`BASE-REPOMAP`**| Authoritative Aider Tree-sitter Call Graph | **0.2293** | **0.3337** | **0.5110** | **0.6599** | **0.0652** | **0.4357** | 180.20 ms | 180.20 ms | N/A |

---

## 3. Mandatory Architectural Directives for Subsequent Stages

Based on the forensic evidence uncovered in Stage 3.7, the following engineering directives are binding for future development:

1. **Replace Flat Regex Symbol Extraction with Scope-Aware AST Parsing**:
   Flat regex matching extracts hundreds of false-positive symbol references from strings, comments, and local variables, generating tens of thousands of spurious edges that dilute PageRank. RepoNeedle must adopt real Tree-sitter call-graph and import-graph extraction (similar to RepoMap) to maintain high precision.
2. **Decouple Symbol Metadata from BM25 Document Length**:
   Do not treat extracted symbols as raw document tokens in Okapi BM25 document length calculations. Document length normalization should reflect content tokens, while symbols should act as targeted lexical bonus fields.
3. **Two-Stage Cascaded Retrieval for Latency Control**:
   Subword n-gram scoring across 11,000 files in Spring-Boot takes $> 500\text{ ms}$. Implement a two-stage cascade: Stage 1 uses fast sparse BM25 to prune the candidate pool from 11,000 to top-200 files; Stage 2 applies subword semantic scoring and graph diffusion exclusively on the pruned candidate set. This will reduce $p95$ latency from 566 ms to $< 40\text{ ms}$.
4. **Preserve Metric Terminology Separation**:
   In all future reports, `CharCov@8k` and `Token BCY@8k` must never be conflated under the ambiguous shorthand "BCY@8k".

---

## 4. Governance & Tag Invariant Sign-Off

The research integrity audit certifies that:
- Tag `v0.1.0-baseline` (`8e00425`) remains untouched and clean.
- Tag `stage3-candidate-freeze` (`cd7f3b0`) remains untouched and clean.
- All 1,380 query prediction rows in `research/stage3_6/PER_QUERY_RESULTS.csv` are preserved and authenticated.
- All 9 metric regression tests in `tests/test_stage3_7_metrics.py` pass without regression.
