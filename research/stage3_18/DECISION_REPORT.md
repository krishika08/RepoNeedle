# RepoNeedle Stage 3.18 — Governance & Forensic Reconciliation Decision Report

**Document ID**: `STAGE3-18-DECISION-001`  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `461f690d5b4bd3c21776eaaf94f038250ee9d6a0`  
**Auditor**: Antigravity Automated Verification Agent  

---

## 1. Formal Governance Decisions

Under the preregistered research charter of Stage 3.18, the audit reaches two formal, distinct verdicts:

### 1.1 Candidate Provenance & Benchmark Reconciliation Verdict
```
================================================================================
VERDICT: RECONCILED — REPRODUCIBLE CANDIDATE LEADERBOARD
================================================================================
```

### 1.2 ContextBench Independent External Validation Gate Verdict
```
================================================================================
CONTEXTBENCH GATE STATUS: BLOCKED — OFFICIAL DATA ACQUISITION
================================================================================
```

---

## 2. Decision Rationale & Core Evidence

### 2.1 Complete Candidate Provenance Established
1. Every candidate identity (`CAND-C`, `CAND-F`, `ARM-101-BASE`, `BASE-BM25`, `BASE-REPOMAP`) is tied to an exact Git commit, architectural source files, graph diffusion formulas, candidate generation constraints, and evaluation hashes.
2. The candidate champion `ARM-101-BASE` was verified directly in source code:
   - Soft lexical damping ($\tau = 0.25$) is verified in [`research/stage3_14/pilot_attenuation.py`](file:///F:/RepoNeedle/research/stage3_14/pilot_attenuation.py#L143-L151).
   - Level 1 verified function call edges (`{"verified_call", "unique_global_call", "intra_file_call"}`) are verified in [`research/stage3_11/function_graph_engine.py`](file:///F:/RepoNeedle/research/stage3_11/function_graph_engine.py).
   - Unattenuated hub weighting ($W_{\text{hub}} = 1.0$) is verified.
3. Candidate F's historical changes were cataloged:
   - Polyglot manifest parsers and English suffix stemming (`_stem`) were preserved in the repo.
   - Non-generalizable hardcoded Ripgrep bypass strings (`"search.rs"`, `"standard.rs"`, and `printer in o_crate`) were excised in commit `9a9944a`.
   - Candidate F's true unconstrained performance on the full corpus collapsed to **$0.1351$ MRR** ($p = 0.0085$ worse than decoupled BM25) due to supernode PageRank dilution.

### 2.2 Historical Metric Discrepancies 100% Reconciled
- All 10 numerical differences between Stage 3.5 and Stage 3.17 have been traced to concrete code refactors (coupled vs decoupled BM25), metric definition shifts (Hit@20 vs multi-target Recall@20), static reference constant replacements (0.2140 constant vs 0.2293 live RepoMap run), candidate pool unconstraining (removal of test-only candidate filtering), or file discovery clamping (`max_files=250` in Caddy RSS profiling).
- Exactly zero discrepancies remain unresolved.

### 2.3 Independent Verification of Candidate F Invalidation
- All 345 positive ARB v2 queries and full repository file corpora were verified in the re-evaluation.
- The forensic origin of the $0.0122$ statistic was uncovered: it originated as the upper bound of the 95% repository-clustered bootstrap confidence interval (`[-0.2014, -0.0122]`) for Recall@5 in Stage 3.10/3.11, which was cited as shorthand in Stage 3.15 summaries.
- Exact live recomputed Wilcoxon test confirms Candidate F is statistically significantly worse than BM25 ($p = 0.008541$), and dominated by `ARM-101-BASE` on 238 of 345 queries ($p = 7.20 \times 10^{-18}$).

### 2.4 ContextBench Gate Remains Appropriately Blocked
- Sandbox network isolation prevents downloading `full.parquet` (1,136 tasks) and `contextbench_verified.parquet` (500 tasks) from Hugging Face (`HTTP Error 403: Forbidden`).
- In strict adherence to research integrity, unofficial mirrors (`Schwerli/ContextBench`) and synthetic Parquet rows are prohibited.
- The ContextBench external validation status remains **`BLOCKED — OFFICIAL DATA ACQUISITION`**.

---

## 3. Authoritative Standardized Leaderboard ($N = 345$ queries, 25 repositories)

| System ID | Role & Status | MRR | Recall@5 | Recall@10 | Recall@20 | Precision@20 | Token BCY@8k | P50 Latency (ms) | P95 Latency (ms) | Process RSS (Caddy) |
|---|---|---|---|---|---|---|---|---|---|---|
| **`BASE-REPOMAP`** | External Reference Leader | **0.2293** | **0.3855** | **0.5275** | **0.6599** | **0.0462** | **0.3177** | 180.20 | 180.20 | 198.0 MB |
| **`ARM-101-BASE`** | **RepoNeedle Candidate Champion** | **0.2078** | **0.3391** | **0.4493** | **0.5648** | **0.0397** | **0.2822** | **12.92** | **130.53** | **198.0 MB** |
| **`BASE-BM25`** | Lexical Baseline | 0.1752 | 0.2928 | 0.3942 | 0.4535 | 0.0322 | 0.2150 | 10.24 | 116.49 | 198.0 MB |
| **`CAND-C`** | Superseded Frozen Candidate | 0.1399 | 0.2319 | 0.3623 | 0.5105 | 0.0355 | 0.2410 | 28.50 | 561.46 | 198.0 MB |
| **`CAND-F`** | **Formally Invalidated Prototype** | 0.1351 | 0.2290 | 0.3594 | 0.5078 | 0.0358 | 0.2336 | 32.42 | 566.28 | 198.0 MB |

---

## 4. Next Steps for the Research Program

1. **Maintain Freeze on `reponeedle/`**: Do not introduce ranking modifications until external independent validation is executed.
2. **ContextBench External Hand-off**: An external operator must acquire the two official Parquet files (revision `c285579`) and place them in `research/external_data/contextbench/`.
3. **Execute Independent Validation**: Once unblocked, evaluate `ARM-101-BASE`, `BASE-BM25`, and `BASE-REPOMAP` on ContextBench without tuning.
