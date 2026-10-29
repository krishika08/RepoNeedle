# RepoNeedle Stage 3.10.2: Canonical Evaluation Integrity Report

**Document ID**: `STAGE3.10.2-INTEGRITY-001`  
**Date**: October 2026  
**Auditor**: Independent Reproducibility & Benchmark Integrity Auditor  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Audited Commit (HEAD)**: [`7679b40`](file:///F:/RepoNeedle)  
**Frozen Baseline Tag** (`v0.1.0-baseline`): [`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`](file:///F:/RepoNeedle)  
**Frozen Candidate Tag** (`stage3-candidate-freeze`): [`cd7f3b01e28695f9a9357e0815069e0eae85baca`](file:///F:/RepoNeedle)  

---

## 1. Executive Verdict & Decision Gate

**OFFICIAL VERDICT: `PASS — CANONICAL RESULTS REPRODUCED`**

### Evidence Supporting Verdict
1. **Per-Query Determinism Verified**:
   Fresh independent processes running deterministic settings reproduced 100% identical ranks, reciprocal ranks, and fractional recalls across all 345 benchmark queries.
2. **Clean-Room Metric Verification**:
   An independent clean-room reference implementation of MRR, Fractional Recall@k, Binary Hit@k, Precision@k, character greedy-stop coverage, and token-budgeted BCY confirmed that all canonical metrics agree within numerical tolerance ($< 10^{-4}$).
3. **Statistical Claims Verified**:
   The published claim that `TEST-GRAPH` improves MRR over `CONTROL-CASCADE` with $p = 0.001$ was verified directly from paired query differences ($W = 87.5, p = 0.000964$, Holm-adjusted $p = 0.00289$). Both query-level and repository-clustered 95% bootstrap intervals strictly exclude zero.
4. **Honest Baseline Position Established**:
   `BASE-REPOMAP` achieves **$0.2293$ MRR** and **$0.6599$ Recall@20** under live evaluation on commit `9e4d689`. RepoNeedle `TEST-GRAPH` achieves **$0.1898$ MRR** and **$0.5605$ Recall@20**. RepoNeedle does not outperform RepoMap overall; its true real-world advantage is latency ($8.30\text{ ms}$ vs. $180.20\text{ ms}$, $21.7\times$ faster).
5. **Memory Scaling Documented**:
   Process RSS is verified at $103.95\text{ MB}$ on `pallets/click` (133 files) and $159.57\text{ MB}$ on `caddyserver/caddy` (555 files). Universal sub-100 MB claims are refuted; memory usage scales proportionally with codebase size.
6. **Full Test Suite Clean**:
   All **150 tests** pass cleanly in $4.4\text{ s}$. Frozen tags remain immutable.

---

## 2. Recomputed Canonical Score Table (N=345 positive ARB v2 queries)

| System ID | Canonical Description | MRR | Recall@5 | Recall@10 | Recall@20 | Hit@20 | char_cov@8k | token_bcy@8k | Latency p50 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BASE-BM25`** | Decoupled Okapi BM25 ($k_1=1.5, b=0.75$) | 0.1752 | 0.2014 | 0.3152 | 0.4535 | 0.5275 | 0.0488 | 0.1971 | 5.54 ms |
| **`CONTROL-CASCADE`** | Stage 3.9 Cascaded Lexical-First Control | 0.1883 | 0.2344 | 0.3665 | 0.5518 | 0.6348 | 0.0488 | 0.2286 | 8.33 ms |
| **`TEST-GRAPH`** | **Cascade + Class-to-Test Invocation Graph** | **0.1898** | **0.2387** | **0.3738** | **0.5605** | **0.6435** | **0.0488** | **0.2286** | **8.30 ms** |
| **`DEGREE-CONTROL`** | Cascade + Bipartite Degree-Matched Random Control | 0.1885 | 0.2373 | 0.3665 | 0.5474 | 0.6319 | 0.0488 | 0.2286 | 8.52 ms |
| **`BASE-REPOMAP`** | Version-Pinned RepoMap (Commit `9e4d689`) | 0.2293 | 0.3337 | 0.5110 | 0.6599 | 0.7478 | 0.0652 | 0.3177 | 180.20 ms |
| **`CAND-C`** | Unconstrained Historical Candidate C | 0.1401 | 0.2024 | 0.3319 | 0.5100 | 0.6029 | 0.0159 | 0.2516 | 31.50 ms |
| **`CAND-F`** | Unconstrained Historical Candidate F | 0.1338 | 0.1824 | 0.3389 | 0.5083 | 0.6000 | 0.0130 | 0.2412 | 32.42 ms |

---

## 3. Error Analysis and Ranking Diagnostics

### 3.1 Task Breakdown
- **`trace2code` (101 queries)**:
  - CONTROL: $0.2646$ MRR, $0.7954$ Recall@20
  - TEST-GRAPH: $0.2674$ MRR, **$0.8152$ Recall@20** ($\Delta = +0.0198$)
  - 14 wins, 3 losses, 84 ties.
  - Test invocation links effectively bridge test files in tracebacks to the production class being tested.
- **`code2test` (106 queries)**:
  - CONTROL: $0.0968$ MRR, $0.3997$ Recall@20
  - TEST-GRAPH: $0.0989$ MRR, **$0.4091$ Recall@20** ($\Delta = +0.0094$)
  - 4 wins, 1 loss, 101 ties.
  - Successfully promotes test files with asymmetric names (e.g. `fastapi` `test_orjson_response_class.py` testing `responses.py`, `gin` `routes_test.go` testing `tree.go`).
- **`comment2context` (80 queries) & `edit2ripple` (58 queries)**:
  - Preserved with zero degradation, protected by the Rank 1–3 BM25 lock.

### 3.2 Representative Win & Loss Analysis
1. **Win**: Query `5f4c149c9f7dac47ebcf685d` (`gin-gonic/gin`, `code2test`):
   - Target: `routes_test.go`
   - Control Rank: 34 (MRR 0.0294, R@20: 0.0)
   - Test Rank: 19 (MRR 0.0526, R@20: 1.0)
   - Mechanism: Direct method call invocation edge from `routes_test.go` to `tree.go` promoted the test by 15 positions into the top-20.
2. **Loss**: Query `a82117a5d29dd98d94ceb931` (`huggingface/transformers`, `code2test`):
   - Target: `tests/models/pe_audio_video/test_modeling_pe_audio_video.py`
   - Control Rank: 4 (MRR 0.2500)
   - Test Rank: 5 (MRR 0.2000)
   - Mechanism: A competing sibling test file also received invocation boost, demoting the target file from rank 4 to rank 5. Both files remained well within the top-10.

---

## 4. Recommendations for Next Engineering Phase (Stage 3.11)

1. **Target Function-Level Production Call Graph**:
   - The remaining gap between RepoNeedle ($0.1898$) and RepoMap ($0.2293$) is function-level call resolution between production files (outside tests).
   - Building a high-precision, package-fenced function call graph should be the primary objective of Stage 3.11.
2. **Preserve Benchmark Integrity Safeguards**:
   - Never reintroduce candidate pre-filtering.
   - Maintain the Rank 1–3 lexical freeze.
   - Maintain separation of character greedy-stop coverage (`char_cov@8k`) and token-budgeted BCY (`token_bcy@8k`).
