# REPONEEDLE STAGE 3.6: BASELINE AND CANDIDATE REPRODUCTION REPORT

**Document ID**: `STAGE3-6-REPRO-001`  
**Date**: October 2026  
**Stage**: Stage 3.6 — Candidate F Reproducibility, Baseline Reconciliation & Evaluation Integrity Audit  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program` / `research/stage3_6-audit`  
**Base Commit**: `4f78cc3` (Stage 3.5)  

---

## 1. REPRODUCTION OBJECTIVE & METHODOLOGY

This report presents the empirical reproduction of RepoNeedle's four central retrieval architectures evaluated across all $N=345$ positive queries of Agent Retrieval Bench (ARB v2):
1. **`BASE-BM25`**: Clean lexical baseline (EXP-016 / Okapi BM25, $k_1=1.5, b=0.75$).
2. **`CAND-C`**: Candidate C (Stage 3.4 frozen candidate: Lexical + Subword Semantic + 0.5x Documentation Penalty).
3. **`CAND-F`**: Candidate F (Stage 3.5 reported winner: Candidate E + Polyglot Symbol Extraction + Manifest-Aware Bi-directional Graph Diffusion).
4. **`BASE-REPOMAP`**: Version-pinned official Aider RepoMap reference (`9e4d689`).

All systems were evaluated under one strictly unified contract:
- Same candidate corpus (no pre-filtering or distractor pruning).
- Same evaluation sample IDs ($N=345$ across 4 tracks: `code2test`, `comment2context`, `trace2code`, `edit2ripple`).
- Same metric definitions (Multi-target fractional recall, standard MRR, token yield under budget).
- Execution without hardcoded string bypasses or synthetic shortcuts.

---

## 2. CANONICAL FOUR-SYSTEM BENCHMARK RESULTS

The empirical reproduction yielded the following canonical performance metrics across all 345 positive tasks:

| System ID | Query Count | MRR | Recall@1 | Recall@5 | Recall@10 | Recall@20 | Precision@5 | Precision@10 | Precision@20 | BCY@4k | BCY@8k | Median Latency (ms) | p95 Latency (ms) | Peak Process RSS (MB) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BASE-BM25`** | 345 | **0.1735** | 0.0464 | 0.1986 | 0.3118 | 0.4549 | 0.0568 | 0.0441 | 0.0322 | 0.0464 | 0.0493 | 20.85 ms | 478.58 ms | 145.2 MB |
| **`CAND-C`** | 345 | **0.1399** | 0.0159 | 0.2111 | 0.3196 | 0.5105 | 0.0557 | 0.0441 | 0.0355 | 0.0159 | 0.0188 | 31.50 ms | 561.46 ms | 168.5 MB |
| **`CAND-F`** | 345 | **0.1351** | 0.0116 | 0.1824 | 0.3316 | 0.5078 | 0.0504 | 0.0452 | 0.0358 | 0.0116 | 0.0159 | 32.42 ms | 566.28 ms | 179.4 MB |
| **`BASE-REPOMAP`** | 345 | **0.2293** | 0.0725 | 0.3337 | 0.5110 | 0.6599 | 0.0186 | 0.0139 | 0.0087 | 0.0326 | 0.0652 | 180.20 ms | 180.20 ms | 265.0 MB |

*Data Source*: [`research/stage3_6/RANKING_RESULTS.csv`](file:///F:/RepoNeedle/research/stage3_6/RANKING_RESULTS.csv) and [`research/stage3_6/PER_QUERY_RESULTS.jsonl`](file:///F:/RepoNeedle/research/stage3_6/PER_QUERY_RESULTS.jsonl).

---

## 3. AUDIT OF CANDIDATE F CLAIMS VS EMPIRICAL REPRODUCTION

| Evaluation Dimension | Stage 3.5 Claimed | Stage 3.6 Reproduced | Variance / Finding | Audit Status |
| :--- | :---: | :---: | :--- | :---: |
| **MRR** | `0.2152` | `0.1351` | **-0.0801 (-37.2%)**; collapses on unconstrained candidate pool | **NOT REPRODUCED** |
| **Recall@5** | `0.2667` | `0.1824` | **-0.0843 (-31.6%)**; inferior to BM25 (0.1986) | **NOT REPRODUCED** |
| **Recall@10** | `0.3942` | `0.3316` | **-0.0626 (-15.9%)**; slight gain over BM25 (0.3118) | **PARTIALLY REPRODUCED** |
| **Recall@20** | `0.5652` | `0.5078` | **-0.0574 (-10.2%)**; reported 0.5652 was binary Hit@20 ($195/345$) | **NOT REPRODUCED** |
| **BCY@8k (All Queries)** | `0.3184` | `0.0159` | **-0.3025 (-95.0%)**; true token yield under strict budget | **NOT REPRODUCED** |
| **BCY@8k (Hit Subset)** | `0.3835` | `0.3835` | Matches only when zero-yield queries are discarded | **EXPLAINED** |
| **Mean Query Latency** | `9.12 ms` | `32.42 ms` | Small warm-query microbenchmarks do not reflect full corpus queries | **INCONCLUSIVE** |
| **Process RSS Ceiling** | `< 100 MB` | `179.4 MB` | Small fixtures passed; real repositories exceed 100 MB | **NOT REPRODUCED** |

---

## 4. PER-TASK STRATUM PERFORMANCE ANALYSIS

Breaking down ranking performance by benchmark track reveals specific failure modes:

| Task Type | Sample Count ($N$) | BM25 MRR | CAND-C MRR | CAND-F MRR | REPOMAP MRR | CAND-F Recall@20 | REPOMAP Recall@20 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`code2test`** | 106 | 0.0685 | 0.0638 | 0.0601 | **0.2284** | 0.3384 | **0.6123** |
| **`comment2context`** | 80 | **0.1657** | 0.1176 | 0.1240 | 0.1590 | 0.3312 | **0.4937** |
| **`trace2code`** | 101 | 0.2487 | 0.2397 | 0.2265 | **0.2829** | 0.7888 | **0.8663** |
| **`edit2ripple`** | 58 | **0.2452** | 0.1356 | 0.1284 | 0.2344 | 0.5718 | **0.6164** |

### Key Observations:
1. **Severe Degradation in `code2test`**: Without artificial candidate pool restriction (`tests_only = True`), Candidate F collapses to $0.0601$ MRR. RepoMap achieves $0.2284$ (+280% higher) because its AST call graph directly links test functions to implementation classes.
2. **Document Length Inflation in `edit2ripple`**: In `edit2ripple`, BM25 scores $0.2452$ MRR, while Candidate F scores $0.1284$ MRR (-47.6%). Appending regex symbols artificially increased document lengths, causing BM25 length normalization penalties on true target files.

---

## 5. REPRODUCTION VERDICT

1. **Candidate F is NOT the development winner**: Candidate F achieves **0.1351 MRR**, which is lower than Candidate C (**0.1399**), lower than BM25 (**0.1735**), and far below RepoMap (**0.2293**).
2. **The Stage 3.5 claims are formally retracted**: All claims that Candidate F outperforms RepoMap or universally operates under 100 MB RSS are refuted by executable evidence on the canonical benchmark.
