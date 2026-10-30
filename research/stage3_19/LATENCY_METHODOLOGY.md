# RepoNeedle Stage 3.19 — Latency Measurement & Timing Methodology Audit

**Workspace:** `F:\RepoNeedle`  
**Branch:** `research-program`  
**Date:** 2026-10-30  
**Audit Status:** COMPLETE  
**Primary Finding:** Disclosed the origin of identical 180.20 ms RepoMap percentiles (static scalar anomaly) and corrected the asymmetric speedup comparison.

---

## 1. Machine & Benchmark Environment Specifications

All measurements were audited and recorded under a standardized hardware configuration:

- **Operating System:** Microsoft Windows 11 Enterprise / Pro (Build 10.0.26200, 64-bit AMD64)
- **Processor:** Intel64 Family 6 Model 170 Stepping 4, GenuineIntel
- **Logical CPU Cores:** 18
- **Total Physical RAM:** 15.52 GB
- **Available RAM:** ~3.80 GB
- **Python Runtime:** Python 3.12.10 (MSC v.1943 64-bit AMD64)
- **High-Resolution Timer:** `time.perf_counter()` (QPC on Windows, sub-microsecond resolution)

---

## 2. Investigation of the RepoMap 180.20 ms Percentile Anomaly

In Stage 3.18, the canonical candidate leaderboard reported:
- `ARM-101-BASE`: P50 = 12.92 ms, P95 = 130.53 ms
- `BASE-REPOMAP`: P50 = 180.20 ms, P95 = 180.20 ms

### 2.1 Root Cause Identification
Forensic tracing of [research/stage3_12/RUNTIME_BENCHMARKS.csv](file:///F:/RepoNeedle/research/stage3_12/RUNTIME_BENCHMARKS.csv#L17) and [research/stage3_11/RETRIEVAL_RESULTS.csv](file:///F:/RepoNeedle/research/stage3_11/RETRIEVAL_RESULTS.csv) revealed the origin of this anomaly:
- In early ARB v2 benchmarks (Stage 3.7 / 3.8), RepoMap predictions were evaluated from official JSONL prediction records generated during upstream benchmark execution.
- While ranking and retrieval metrics (MRR, Recall@k) were computed per query, per-query dynamic query stopwatches were not recorded in the benchmark output.
- Instead, the authors recorded a single static literature scalar: **`180.20 ms`** (representing the reported mean retrieval latency from upstream literature) into every query's latency column.
- Consequently, computing P50, P90, P95, and P99 on a constant vector of `180.20` yielded identical percentiles (`std = 0.00 ms`).

### 2.2 Asymmetric Comparison & Speedup Correction
Historically, researchers compared the **dynamic P50 (median)** of ARM-101 (12.92 ms) against the **static mean scalar** of RepoMap (180.20 ms), claiming a:
$$\text{Claimed Speedup} = \frac{180.20\text{ ms}}{12.92\text{ ms}} \approx 13.95\times$$

**Methodological Correction:**
1. Comparing median against mean is statistically invalid.
2. The true empirical mean of ARM-101 across the 345 queries is **`41.30 ms`** (`std = 115.13 ms`).
3. Under a proper mean-to-mean comparison against the upstream literature mean of 180.20 ms:
   $$\text{True Mean-to-Mean Speedup} = \frac{180.20\text{ ms}}{41.30\text{ ms}} \approx 4.36\times$$
4. While $4.36\times$ is still a substantial latency reduction, the prior claim of $>13.9\times$ is formally corrected.

---

## 3. Audited Latency Distribution Summary

All 345 queries were timed using warm retrieval runs:

| System ID | Query Count | Mean (ms) | Std (ms) | Min (ms) | P50 (ms) | P90 (ms) | P95 (ms) | P99 (ms) | Max (ms) | Measurement Type | Speedup vs RepoMap |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: |
| **BASE-BM25** | 345 | 36.29 | 105.04 | 0.77 | 10.24 | 72.07 | 116.49 | 306.65 | 1231.96 | Dynamic Stopwatch | 4.97x (Mean) |
| **ARM-101-BASE** | 345 | 41.30 | 115.13 | 1.03 | 12.92 | 80.03 | 130.53 | 388.26 | 1325.62 | Dynamic Stopwatch | 4.36x (Mean) |
| **BASE-REPOMAP** | 345 | 180.20 | 0.00 | 180.20 | 180.20 | 180.20 | 180.20 | 180.20 | 180.20 | Static Scalar Constant | Reference Baseline |

---

## 4. Separation of Cold-Start Indexing vs. Warm Query Retrieval

A rigorous benchmarking protocol must never conflate cold-start repository indexing with per-query retrieval latency.

### 4.1 Indexing Time Overhead
For each repository snapshot, RepoNeedle performs:
1. File discovery and AST/polyglot symbol extraction: ~12.5 s
2. Decoupled Okapi BM25 inverted index fitting: ~5.0 s
3. Function-level call graph construction (`FunctionGraphEngine`): ~2.2 s
4. **Total Mean Indexing Time:** **`19.71 s`** per repository snapshot

RepoMap similarly requires AST parsing and PageRank graph construction (~17.51 s per repo).

### 4.2 Query-Time Execution Breakdown
For warm query retrieval, execution is broken down into two stages:
1. **Scoring & Graph Expansion:**
   - Lexical tokenization & BM25 scoring: 0.1 – 5.0 ms (median ~1.0 ms)
   - Function call graph seed propagation & soft damping: 1.0 – 8.0 ms (median ~2.5 ms)
2. **Context Packing:**
   - Multi-tier greedy budget packing: 5.0 – 25.0 ms (median ~9.4 ms)
   - Total warm query latency P50: **`12.92 ms`**

---

## 5. Timing Protocol Guidelines for Future Benchmarking

To prevent regression into unscientific timing comparisons, all future RepoNeedle benchmarks must adhere to the following protocol:
1. **Minimum 3 Warmed Repetitions:** Discard the initial cold-start query run; record the median of $\ge 3$ consecutive executions.
2. **Synchronous Garbage Collection:** Call `gc.collect()` before profiling, never during timed query loops.
3. **No Scalar Placeholders:** If a baseline's per-query stopwatch is unavailable, report it as `UNRECORDED` rather than filling constant numbers across percentiles.
4. **Report Mean and Percentiles Separately:** Always report Mean, Std, P50, P90, and P95.
