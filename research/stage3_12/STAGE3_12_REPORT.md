# RepoNeedle Stage 3.12 — Performance Hardening, Fair Benchmarking & Evidence Closure Report

## Executive Summary & Final Verdicts

Stage 3.12 concludes the performance hardening, fair runtime benchmarking, and empirical evidence closure for the RepoNeedle research programme on branch `research-program` (starting commit `59e77e6`).

This stage resolves historical measurement ambiguities, eliminates algorithmic bottlenecks through mathematically equivalent optimizations, provides an auditable accounting of all benchmark claims, and establishes clear operating policies for deployment in AI coding agents.

### Separate Verdicts Across Key Research Dimensions

| Dimension | Canonical Verdict | Supporting Evidence |
|---|---|---|
| **Retrieval Quality vs. BM25** | **VERIFIED IMPROVEMENT** | CONFIG-09 improves MRR from **0.1759 to 0.2061** (+17.2%, Holm $p = 0.00063$), Recall@20 from **0.4622 to 0.5576**, and Token BCY@8k from **0.2121 to 0.2729**. |
| **Retrieval Quality vs. RepoMap** | **REPOMAP LEADS ON ARB v2** | Official RepoMap achieves **0.2293 MRR** and **0.6599 Recall@20** vs. RepoNeedle's 0.2061 MRR. RepoNeedle does **not** claim superiority over RepoMap in headline retrieval quality on ARB v2. |
| **Quality Parity (CONFIG-10 vs 09)** | **VERIFIED PARITY (98.0% MRR)** | CONFIG-10 achieves **0.2019 MRR** (difference $-0.0042$, 95% CI $[-0.0125, +0.0039]$, Wilcoxon $p = 0.297$, statistically indistinguishable from CONFIG-09). |
| **Runtime Performance** | **REAL-WORLD ACCELERATION** | BM25 inverted postings list achieves **24.9x scoring speedup** (<0.15 ms); semantic candidate slicing cuts matrix operations by **13.6x**. Warm retrieval scoring is sub-millisecond. |
| **Historical Claims Audit** | **EVIDENCE CLOSED / RECONCILED** | 3 historical claims formally withdrawn (23.2ms vs 180.2ms latency, 3.9x Precision@5, Candidate F win); 2 methodology errors reconciled; 3 claims verified valid. |
| **Independent Validation Gate** | **BLOCKED / PRELIMINARY** | External access to ContextBench is blocked by standard sandbox security (`HTTP 403 Forbidden`). ARB v2 remains development evidence only. |

---

## 1. Repository Integrity Verification (Phase 0)

Before executing any benchmark or code changes:
1. **Branch**: `research-program`
2. **Starting Commit**: `59e77e66d4a26cc85f58a573eaac4a79432e93c1` (`59e77e6`)
3. **Frozen Tags Verified**:
   - `v0.1.0-baseline`: `8e00425a1768822650059e6ea3565074cbca6117` (UNMODIFIED)
   - `stage3-candidate-freeze`: `cd7f3b0fe16091217e92828b6d080c55490fd38c` (UNMODIFIED)
4. All work is isolated in `research/stage3_12/` and existing historical files in `research/stage3_11/`, `stage3_10/`, `stage3_9/`, `stage3_8/`, `stage3_7/`, and `stage3_6/` remain intact.

---

## 2. Canonical Performance Comparison (Phase 1)

The canonical performance across the $N=345$ positive ARB v2 queries is reproduced below with zero fabricated proxies, zero literature scalar substitutions, and full metric alignment:

| System ID | Config ID | Description | Query Count | MRR | Recall@5 | Recall@10 | Recall@20 | Precision@5 (Untruncated) | Token BCY@8k | Status |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **BASE-BM25** | `CONFIG-01` | Official BM25 Baseline (Okapi k1=1.5, b=0.75) | 345 | 0.1759 | 0.1990 | 0.3234 | 0.4622 | 0.0568 | 0.2121 | Canonical Baseline |
| **CONFIG-09** | `CONFIG-09` | Decoupled BM25 + Subword Semantic + DocFilter (No PR) | 345 | 0.2061 | 0.2512 | 0.3767 | 0.5576 | 0.0725 | 0.2729 | Holm $p = 0.00063$ vs BM25 |
| **CONFIG-10** | `CONFIG-10` | Sparse Top-50 BM25 + Sliced Subword Reranking | 345 | 0.2019 | 0.2459 | 0.3776 | 0.5494 | 0.0713 | 0.2633 | Parity with CONFIG-09 ($p=0.297$) |
| **BASE-REPOMAP** | `BASE-REPOMAP` | Version-Pinned RepoMap (commit 9e4d689, AST PageRank) | 345 | 0.2293 | 0.3337 | 0.5110 | 0.6599 | 0.0910 | 0.3177 | Benchmark Leader |

### Key Retrieval Conclusions
1. **RepoNeedle is demonstrably superior to pure BM25**: CONFIG-09 provides $+17.2\%$ higher MRR ($0.2061$ vs $0.1759$), $+20.6\%$ higher Recall@20 ($0.5576$ vs $0.4622$), and $+28.7\%$ higher Token BCY@8k ($0.2729$ vs $0.2121$). All gains survive multiplicity control via Holm's step-down procedure.
2. **RepoMap remains the benchmark leader on ARB v2**: RepoMap achieves $0.2293$ MRR and $0.6599$ Recall@20, outperforming CONFIG-09 by $+0.0232$ MRR ($+11.3\%$). RepoNeedle honestly acknowledges RepoMap's structural retrieval superiority.
3. **CONFIG-10 achieves statistical parity with CONFIG-09**: The difference of $-0.0042$ MRR is statistically indistinguishable from zero ($p = 0.297$, CI includes zero), while delivering up to 2x scoring speedups on large codebases.

---

## 3. Auditing & Repairing Runtime Claims (Phase 2)

All historical claims have been audited and cataloged in [CLAIM_EVIDENCE_LEDGER.csv](file:///F:/RepoNeedle/research/stage3_12/CLAIM_EVIDENCE_LEDGER.csv).

### Forensic Findings on Withdrawn Claims

1. **Withdrawal of the "23.20 ms vs 180.20 ms" Latency Comparison**:
   - In Stage 3.10, RepoMap's p50 and p95 latency were reported as exactly `180.20 ms`.
   - Audit revealed that `180.20 ms` was **not dynamically measured per query** on the evaluation machine. It was a hardcoded static scalar imported from external benchmark documentation into `evaluate_systems.py`.
   - Comparing dynamic stopwatch times in Python against an external static constant is methodologically invalid.
   - **Correction**: The claim of a "7.8x speedup over RepoMap" is formally withdrawn.

2. **Withdrawal of the "3.9x Precision@5" Advantage**:
   - In Stage 3.10, RepoMap's `Precision@5` was reported as `0.0186` compared to RepoNeedle's `0.0725` (claimed 3.9x win).
   - Audit in Stage 3.11 revealed that the upstream ARB v1.1 details JSON omitted the precision key for several repositories, returning default zero values.
   - Recomputing Precision@5 directly from the top-5 ranked paths demonstrates that RepoMap's true Precision@5 is **0.0910**, which is higher than RepoNeedle's ($0.0725$).
   - **Correction**: The claim of higher Precision@5 is formally withdrawn. RepoMap has $+25.5\%$ higher Precision@5.

3. **Clarification on RepoMap Local Execution**:
   - Stage 3.4/3.5 commentary suggested RepoMap required external LLM API calls.
   - Source inspection confirms RepoMap uses local tree-sitter AST parsing, ctags-style symbol extraction, and PageRank over co-occurrence graphs. It requires **zero external LLM calls or API keys**.

4. **Reconciliation of Engine Timing Boundaries**:
   - In earlier versions of `engine.py`, `res.execution_time_ms` was captured before context packing (`budget_optimizer.pack_context`), creating timing boundary confusion.
   - Stage 3.12 explicitly measures and isolates:
     - `scoring_latency_ms`: Inverted BM25 + subword matrix operations (0.1 - 3.0 ms).
     - `packing_latency_ms`: AST skeletonization + knapsack token budgeting (5.0 - 15.0 ms).
     - `e2e_latency_ms`: Total end-to-end retrieve() invocation.

---

## 4. Real Bottleneck Profiling & Hardening (Phases 3 & 4)

Profiling revealed that previous implementations suffered from $O(N)$ linear scans across the entire document corpus during BM25 scoring and unconstrained matrix-vector multiplications across thousands of rows in subword semantic scoring.

### Optimizations Implemented & Mathematically Verified

1. **Inverted Postings List in `reponeedle/core/lexical.py`**:
   - Replaced linear document term-frequency iteration with an inverted index mapping tokens to sparse postings: `self.inverted_index[token] = [(doc_idx, tf), ...]`.
   - Precomputed document length normalization factors: `self.doc_len_norms = 1.0 - b + b * (doc_lengths / avg_doc_len)`.
   - **Bitwise Parity**: Floating-point scores are 100% bitwise identical to the baseline Okapi BM25 implementation.
   - **Speedup**: **24.9x speedup** on 5,000 documents (reduced from $2.94$ ms to $0.118$ ms).

2. **Candidate-Restricted Sparse Slicing in `reponeedle/core/semantic.py`**:
   - Added `candidate_indices: Optional[Sequence[int]]` parameter to `SubwordSemanticIndex.score()`.
   - When provided, the sparse CSR document matrix is sliced `doc_matrix[candidate_indices]`, restricting matrix dot-product operations to only the top candidate rows.
   - Added LRU query vector cache (`_query_cache`, maxsize=128) with automatic cache clearing on `fit()`.
   - **Speedup**: **13.6x speedup** on 10,000 documents (reduced from $2.02$ ms to $0.148$ ms).

3. **Cascaded Engine Integration in `reponeedle/engine.py`**:
   - Added `candidate_pool_size: Optional[int]` to `AblationConfig` and `RepoNeedleEngine.retrieve()`.
   - When set, BM25 scores the corpus via inverted index in $<0.2$ ms, identifies the top-K candidate indices, and passes them to the subword semantic ranker.

---

## 5. Multi-Scale Empirical Benchmarks (Phase 4)

Profiling was conducted across 5 repository scale tiers from 119 to 1,435 files using Windows PSAPI (`WorkingSetSize`) and Python object memory inspection.

### Runtime Latency Breakdown Across Scale Tiers

| Repository | Scale Category | File Count | LOC | Configuration | Index Fit (ms) | Cold Query (ms) | Warm p50 (ms) | Warm p95 (ms) | Scoring p50 (ms) | Packing p50 (ms) |
|---|---|:---:|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `pallets/click` | Small (Python) | 133 | 14,092 | BASE-BM25 | 16.5 | 4.8 | 3.2 | 4.5 | 0.12 | 3.1 |
| `pallets/click` | Small (Python) | 133 | 14,092 | CONFIG-09 | 24.2 | 7.9 | 5.4 | 6.8 | 0.61 | 4.8 |
| `pallets/click` | Small (Python) | 133 | 14,092 | CONFIG-10 | 23.8 | 8.1 | 5.6 | 7.0 | 0.65 | 4.9 |
| `gin-gonic/gin` | Medium (Go) | 119 | 11,756 | BASE-BM25 | 14.2 | 4.5 | 3.1 | 4.2 | 0.11 | 3.0 |
| `gin-gonic/gin` | Medium (Go) | 119 | 11,756 | CONFIG-09 | 21.0 | 7.2 | 5.1 | 6.5 | 0.58 | 4.5 |
| `gin-gonic/gin` | Medium (Go) | 119 | 11,756 | CONFIG-10 | 20.8 | 7.4 | 5.2 | 6.6 | 0.62 | 4.6 |
| `tokio-rs/tokio` | Medium (Rust) | 812 | 94,743 | BASE-BM25 | 128.4 | 12.1 | 8.4 | 11.2 | 0.38 | 8.0 |
| `tokio-rs/tokio` | Medium (Rust) | 812 | 94,743 | CONFIG-09 | 185.6 | 18.4 | 14.2 | 17.8 | 3.18 | 11.0 |
| `tokio-rs/tokio` | Medium (Rust) | 812 | 94,743 | CONFIG-10 | 184.2 | 15.2 | 11.8 | 15.0 | 1.69 | 10.1 |
| `caddyserver/caddy`| Med/Large (Go) | 555 | 73,837 | BASE-BM25 | 92.1 | 10.5 | 7.2 | 9.8 | 0.28 | 6.9 |
| `caddyserver/caddy`| Med/Large (Go) | 555 | 73,837 | CONFIG-09 | 142.5 | 16.2 | 12.5 | 15.6 | 2.45 | 10.0 |
| `caddyserver/caddy`| Med/Large (Go) | 555 | 73,837 | CONFIG-10 | 140.8 | 13.8 | 10.4 | 13.2 | 1.48 | 8.9 |
| `etcd-io/etcd` | Large (Go) | 1,435 | 214,500 | BASE-BM25 | 285.0 | 18.2 | 12.8 | 16.5 | 0.65 | 12.1 |
| `etcd-io/etcd` | Large (Go) | 1,435 | 214,500 | CONFIG-09 | 410.2 | 28.5 | 22.4 | 28.1 | 6.82 | 15.6 |
| `etcd-io/etcd` | Large (Go) | 1,435 | 214,500 | CONFIG-10 | 405.6 | 21.0 | 16.5 | 21.2 | 2.15 | 14.3 |

### Memory Consumption Across Scale Tiers

| Repository | File Count | Configuration | Python Heap (MB) | Heap Peak (MB) | Process RSS (MB) | RSS Peak (MB) |
|---|:---:|---|:---:|:---:|:---:|:---:|
| `pallets/click` | 133 | CONFIG-09 / 10 | 2.45 | 4.80 | 124.5 | 132.0 |
| `gin-gonic/gin` | 119 | CONFIG-09 / 10 | 2.10 | 4.20 | 124.6 | 132.0 |
| `tokio-rs/tokio` | 812 | CONFIG-09 / 10 | 14.80 | 28.50 | 245.2 | 268.0 |
| `caddyserver/caddy`| 555 | CONFIG-09 / 10 | 10.20 | 19.80 | 210.5 | 230.0 |
| `etcd-io/etcd` | 1,435 | CONFIG-09 / 10 | 32.40 | 58.20 | 335.8 | 362.0 |

---

## 6. Quality-Speed Trade-Off & Deployment Operating Policy (Phase 5)

Evaluation of candidate pool sizes ($K \in [10, 25, 50, 100, 200, \text{Full}]$) across all 345 positive ARB v2 queries demonstrates a smooth Pareto trade-off curve (see [QUALITY_SPEED_TRADEOFF.csv](file:///F:/RepoNeedle/research/stage3_12/QUALITY_SPEED_TRADEOFF.csv)).

### Deployment Policy Rules

```mermaid
flowchart TD
    Start["New Retrieval Query"] --> CheckSize{"Repository File Count"}
    CheckSize -- "< 500 files" --> C09["Use CONFIG-09 (Full Hybrid)<br/>- Maximal Recall Ceiling (0.5576)<br/>- Scoring latency < 1.0 ms"]
    CheckSize -- ">= 500 files" --> CheckSLA{"Latency SLA"}
    CheckSLA -- "Standard Interactive" --> C10_50["Use CONFIG-10 (K=50)<br/>- 98.0% MRR Retention<br/>- 2x-3x Scoring Speedup"]
    CheckSLA -- "Strict Real-Time (<10ms)" --> C10_25["Use CONFIG-10 (K=25)<br/>- 96.3% MRR Retention<br/>- 0.42x Scoring Cost"]
    CheckSLA -- "Batch / Enterprise Quality" --> C10_100["Use CONFIG-10 (K=100)<br/>- 99.4% MRR Retention<br/>- Recovers 80% of Tail Drops"]
```

1. **Small-to-Medium Repositories (< 500 files)**: Default to **CONFIG-09**. Subword scoring is already sub-millisecond, and full hybrid guarantees maximum recall.
2. **Large Monolithic Repositories (>= 500 files)**: Default to **CONFIG-10 ($K=50$)**. Cuts scoring time by up to $3\times$ while preserving statistical parity with CONFIG-09 ($p = 0.297$).
3. **High-Recall Enterprise Policy**: Use **CONFIG-10 ($K=100$)** on repositories exceeding 2,000 files to eliminate candidate boundary drops while avoiding linear matrix scaling.

---

## 7. Independent Validation Gate Status (Phase 6)

- **Target Dataset**: ContextBench (`https://huggingface.co/datasets/Contextbench/ContextBench`)
- **Probed Status**: `HTTP Error 403: Forbidden` (Access denied under secure execution sandbox).
- **Official Verdict**: **BLOCKED / PRELIMINARY**.
- **Integrity Rule**: RepoNeedle strictly adheres to research integrity guidelines. External benchmarks are not scraped or simulated via unvalidated proxies. ARB v2 remains strictly development evidence. When unsandboxed network permission is granted by the user, an automated validation run can be executed.

---

## 8. Summary of Stage 3.12 Deliverables (Phase 7)

All required deliverables are committed and linked below:

1. [CANONICAL_REPRODUCTION.csv](file:///F:/RepoNeedle/research/stage3_12/CANONICAL_REPRODUCTION.csv): Aligned comparison of BM25, CONFIG-09, CONFIG-10, and RepoMap across 345 queries.
2. [RUNTIME_BENCHMARKS.csv](file:///F:/RepoNeedle/research/stage3_12/RUNTIME_BENCHMARKS.csv): Multi-tier empirical latency breakdown isolating scoring from packing.
3. [MEMORY_BENCHMARKS.csv](file:///F:/RepoNeedle/research/stage3_12/MEMORY_BENCHMARKS.csv): Heap vs Windows PSAPI Process Working Set memory profiling.
4. [QUALITY_SPEED_TRADEOFF.csv](file:///F:/RepoNeedle/research/stage3_12/QUALITY_SPEED_TRADEOFF.csv): Pareto curves across candidate pool sizes.
5. [CLAIM_EVIDENCE_LEDGER.csv](file:///F:/RepoNeedle/research/stage3_12/CLAIM_EVIDENCE_LEDGER.csv): Forensic audit and disposition of 8 historical benchmark claims.
6. [FAILURE_ANALYSIS.md](file:///F:/RepoNeedle/research/stage3_12/FAILURE_ANALYSIS.md): Query-by-query root cause analysis of CONFIG-10 candidate cutoffs.
7. [REPRODUCE.md](file:///F:/RepoNeedle/research/stage3_12/REPRODUCE.md): Exact reproduction commands and instructions.
8. [EXPERIMENT_REGISTRY.jsonl](file:///F:/RepoNeedle/research/stage3_12/EXPERIMENT_REGISTRY.jsonl): Machine-readable registry of Stage 3.12 experiments.
9. [STAGE3_12_REPORT.md](file:///F:/RepoNeedle/research/stage3_12/STAGE3_12_REPORT.md): This authoritative report.
10. Automated tests: [test_stage3_12_hardening.py](file:///F:/RepoNeedle/tests/test_stage3_12_hardening.py).
