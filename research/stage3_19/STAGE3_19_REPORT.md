# RepoNeedle Stage 3.19 — Production Parity, Independent Reproduction & Performance Integrity Audit

**Workspace:** `F:\RepoNeedle`  
**Branch:** `research-program`  
**Starting Commit:** `c688516f974ddf61e5b15f49f083aa412376e64c` (Stage 3.18)  
**Date:** 2026-10-30  
**Status:** COMPLETE & AUTHORITATIVE  
**Formal Governance Verdict:** **`B. INTERNALLY REPRODUCIBLE BUT NOT PRODUCTION-INTEGRATED`**  
**External Benchmark Gate:** **`BLOCKED — OFFICIAL DATA ACQUISITION`**

---

## 1. Executive Summary & Research Mandate

Stage 3.19 was initiated to resolve the critical engineering and scientific questions confronting RepoNeedle after the historical forensic reconciliations of Stages 3.15–3.18:
1. **Production Parity:** Does the actual installed/importable RepoNeedle package execute the same `ARM-101-BASE` architecture that achieved the $0.2078$ MRR development benchmark?
2. **Deterministic Clean Reproduction:** Can the reported metrics of `ARM-101-BASE`, `BASE-BM25`, and `BASE-REPOMAP` be reproduced bit-for-bit from authentic ARB v2 positive queries without shortcuts or pre-filtering?
3. **Latency Integrity:** Why did RepoMap have identical P50 and P95 latency percentiles ($180.20\text{ ms}$), and what is the true empirical speedup of RepoNeedle?
4. **Memory Scalability:** What is the true operating system Process Resident Set Size (RSS) across small and large codebases when full files are indexed without artificial file clamping?
5. **Statistical Precision:** Under cluster-aware bootstrap resampling, does ARM-101 statistically outperform BM25, and does it demonstrate equivalence or non-inferiority to RepoMap?
6. **Documentation & Claim Reconciliation:** Are all superseded historical claims cleanly registered and invalidated?
7. **External Benchmark Readiness:** Is the official ContextBench ingestion pipeline defined and cryptographically frozen?

---

## 2. Core Audit Findings Across All Seven Phases

### Phase 1: Candidate Provenance & Production Parity Audit
- **Finding:** `ARM-101-BASE` is strictly an unintegrated research prototype.
- **Evidence:**
  - Implemented in [research/stage3_14/pilot_attenuation.py](file:///F:/RepoNeedle/research/stage3_14/pilot_attenuation.py) (`ExperimentalLanguageRanker`) and [research/stage3_11/function_graph_engine.py](file:///F:/RepoNeedle/research/stage3_11/function_graph_engine.py) (`FunctionGraphEngine`).
  - Production source code under `reponeedle/` contains **zero** occurrences of `ARM-101`, `FunctionGraphEngine`, or soft damping parameter `soft_damping_tau`.
  - The installed application CLI ([reponeedle/cli.py](file:///F:/RepoNeedle/reponeedle/cli.py)) and main API ([reponeedle/engine.py](file:///F:/RepoNeedle/reponeedle/engine.py)) execute legacy router-based linear combination ($0.1399$ MRR) or pure Okapi BM25 ($0.1752$ MRR).
  - While `reponeedle/core/cascade.py` contains `CascadedRanker` ($0.1897$ MRR), even `CascadedRanker` is disconnected from `RepoNeedleEngine.retrieve()`.
- **Deliverable:** [research/stage3_19/PRODUCTION_PARITY_AUDIT.md](file:///F:/RepoNeedle/research/stage3_19/PRODUCTION_PARITY_AUDIT.md)

### Phase 2: Clean-Checkout Reproduction
- **Finding:** Canonical ARB v2 benchmark metrics for `ARM-101-BASE` ($0.2078$ MRR), `BASE-BM25` ($0.1752$ MRR), and `BASE-REPOMAP` ($0.2293$ MRR) reproduced with 100% precision across all 345 positive benchmark queries and 218 snapshots.
- **Evidence:**
  - Zero candidate shortlist pre-filtering.
  - Zero oracle routing based on gold targets.
  - Zero artificial file clipping.
- **Deliverables:**
  - [research/stage3_19/CLEAN_REPRODUCTION.md](file:///F:/RepoNeedle/research/stage3_19/CLEAN_REPRODUCTION.md)
  - [research/stage3_19/REPRODUCED_LEADERBOARD.csv](file:///F:/RepoNeedle/research/stage3_19/REPRODUCED_LEADERBOARD.csv)
  - [research/stage3_19/PER_QUERY_RESULTS.csv](file:///F:/RepoNeedle/research/stage3_19/PER_QUERY_RESULTS.csv)
  - [research/stage3_19/REPRODUCTION_HASHES.csv](file:///F:/RepoNeedle/research/stage3_19/REPRODUCTION_HASHES.csv)

### Phase 3: Latency Measurement & Timing Audit
- **Finding:** The identical RepoMap percentiles ($180.20\text{ ms}$ for P50, P90, P95, P99) were caused by populating every query's latency column with a single static literature mean scalar.
- **Speedup Correction:**
  - Comparing ARM-101's dynamic median ($12.92\text{ ms}$) to RepoMap's static mean ($180.20\text{ ms}$) incorrectly claimed a $>13.9\times$ speedup.
  - The true empirical mean query latency of ARM-101 across the 345 queries is **`41.30 ms`** (`std = 115.13 ms`).
  - True mean-to-mean speedup against the upstream literature mean of 180.20 ms is **`4.36x`**.
  - Mean cold-start indexing overhead is **`19.71 s`** per repository, which must be clearly separated from query retrieval.
- **Deliverables:**
  - [research/stage3_19/LATENCY_METHODOLOGY.md](file:///F:/RepoNeedle/research/stage3_19/LATENCY_METHODOLOGY.md)
  - [research/stage3_19/LATENCY_RAW.csv](file:///F:/RepoNeedle/research/stage3_19/LATENCY_RAW.csv)
  - [research/stage3_19/LATENCY_SUMMARY.csv](file:///F:/RepoNeedle/research/stage3_19/LATENCY_SUMMARY.csv)

### Phase 4: Memory & Scalability Audit
- **Finding:** The historical universal $<100\text{ MB}$ process memory claim was achieved by artificially capping Caddy to 250 files and truncating file content to 25,000 characters.
- **True Operating Set:**
  - On full unconstrained Caddy (605 files), isolated process RSS is **`198.0 MB`** (peak working set **`272.8 MB`**).
  - On large repositories like `etcd-io/etcd` (1,431 files), isolated process RSS reaches **`364.1 MB`** (peak working set **`609.2 MB`**).
  - Python heap allocated for index data structures is $<20\text{ MB}$, but CPython runtime, NumPy arrays, SciPy CSR matrices, and OS memory management require $180\text{--}350\text{ MB}$ of working set. Python heap must never be substituted for Process RSS.
- **Deliverables:**
  - [research/stage3_19/MEMORY_SCALABILITY_AUDIT.md](file:///F:/RepoNeedle/research/stage3_19/MEMORY_SCALABILITY_AUDIT.md)
  - [research/stage3_19/MEMORY_SCALABILITY.csv](file:///F:/RepoNeedle/research/stage3_19/MEMORY_SCALABILITY.csv)

### Phase 5: Statistical Integrity & Resampling Audit
- **Finding:** 10,000 cluster-aware bootstrap replicates (sampling 25 repositories with replacement, fixed seed `42`):
  - `ARM-101-BASE vs BASE-BM25`: $\Delta\text{MRR} = +0.0325$, 95% Clustered CI $[+0.0238, +0.0443]$, empirical bootstrap bound **`p < 0.0001`** (zero exceedances out of 10,000), Wilcoxon paired $p = 6.41 \times 10^{-31}$. Superiority is confirmed.
  - `ARM-101-BASE vs BASE-REPOMAP`: $\Delta\text{MRR} = -0.0244$, 95% Clustered CI $[-0.0741, +0.0176]$, empirical bootstrap $p = 0.3234$, Wilcoxon paired $p = 0.0559$. Superiority is rejected.
- **The Equivalence Fallacy:** Because the 95% CI includes substantial penalties (down to $-0.0741$ MRR) and RepoMap achieves 178 wins vs 140 losses, non-significance does **not** prove equivalence. Equivalence claims are formally rejected.
- **Deliverables:**
  - [research/stage3_19/STATISTICAL_AUDIT.md](file:///F:/RepoNeedle/research/stage3_19/STATISTICAL_AUDIT.md)
  - [research/stage3_19/PAIRWISE_COMPARISONS.csv](file:///F:/RepoNeedle/research/stage3_19/PAIRWISE_COMPARISONS.csv)
  - [research/stage3_19/REPOSITORY_LEVEL_RESULTS.csv](file:///F:/RepoNeedle/research/stage3_19/REPOSITORY_LEVEL_RESULTS.csv)

### Phase 6: Claim and Documentation Reconciliation
- **Finding:** Registered 8 historical research claims in the authoritative claim status register:
  - `Candidate F MRR 0.2152` $\to$ `FORMALLY_INVALIDATED`
  - `Candidate C MRR 0.2040` $\to$ `SUPERSEDED_NON_CANONICAL`
  - `RepoMap MRR 0.2140` $\to$ `SUPERSEDED_HARDCODED_CONSTANT`
  - `Universal Process RSS < 100 MB` $\to$ `FORMALLY_INVALIDATED`
  - `ARB v2 proves independent generalization` $\to$ `FORMALLY_INVALIDATED`
  - `Equivalence to RepoMap` $\to$ `FORMALLY_INVALIDATED`
  - `13.9x speedup over RepoMap` $\to$ `SUPERSEDED_ASYMMETRIC_COMPARISON`
  - `ARM-101 Production Champion` $\to$ `SUPERSEDED_UNINTEGRATED_PROTOTYPE`
- **Deliverables:**
  - [research/stage3_19/CLAIM_STATUS_REGISTER.csv](file:///F:/RepoNeedle/research/stage3_19/CLAIM_STATUS_REGISTER.csv)
  - [research/stage3_19/STAGE3_19_DECISION_REPORT.md](file:///F:/RepoNeedle/research/stage3_19/STAGE3_19_DECISION_REPORT.md)

### Phase 7: External Benchmark Readiness & Governance
- **Finding:** Pinned upstream official ContextBench dataset (`full.parquet`, `contextbench_verified.parquet` at revision `c285579`) remains blocked by current sandbox/environment network limits.
- **Governance Action:** Preserved external validation gate as **`BLOCKED — OFFICIAL DATA ACQUISITION`**. Zero unofficial substitutes or synthetic datasets permitted.
- **Deliverable:** [research/stage3_19/CONTEXTBENCH_IMPORT_AND_READINESS.md](file:///F:/RepoNeedle/research/stage3_19/CONTEXTBENCH_IMPORT_AND_READINESS.md)

---

## 3. Authoritative Candidate Leaderboard (ARB v2 Development Benchmark)

| Candidate / System ID | Status | Architectural Summary | MRR | Recall@5 | Recall@10 | Recall@20 | Precision@20 | Token BCY@4k | Token BCY@8k | P50 Latency (ms) | P95 Latency (ms) | Mean Latency (ms) | Process RSS (MB) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BASE-REPOMAP** | External Reference Leader | Official Aider RepoMap reference (commit 9e4d689) with AST PageRank | **0.2293** | **0.3855** | **0.5275** | **0.6599** | **0.0462** | **0.2185** | **0.3177** | 180.20* | 180.20* | 180.20 | 198.0 |
| **ARM-101-BASE** | Research Candidate (Unintegrated) | Soft Lexical Damping ($\tau=0.25$) + Level-1 Verified Call Edges | 0.2078 | 0.3391 | 0.4493 | 0.5648 | 0.0397 | 0.1840 | 0.2822 | 12.92 | 130.53 | 41.30 | 198.0 |
| **CONTROL-CASCADE** | Intermediate Baseline | CascadedRanker: Top-3 hard lexical freeze + bounded graph expansion | 0.1897 | 0.3120 | 0.4180 | 0.5217 | 0.0368 | 0.1690 | 0.2540 | 13.11 | 135.23 | 42.74 | 198.0 |
| **BASE-BM25** | Lexical Baseline (Production) | Decoupled Okapi BM25 length-normalized scoring ($k_1=1.5, b=0.75$) | 0.1752 | 0.2928 | 0.3942 | 0.4535 | 0.0322 | 0.1538 | 0.2150 | **10.24** | **116.49** | **36.29** | **112.7** |
| **CAND-C** | Superseded Baseline (Default API) | Stage 3 freeze: BM25 + subwords + 0.5x doc filter + PageRank fusion | 0.1399 | 0.2319 | 0.3623 | 0.5105 | 0.0355 | 0.1620 | 0.2410 | 28.50 | 561.46 | 84.20 | 198.0 |
| **CAND-F** | Formally Invalidated | Stage 3.5: Polyglot graph + PageRank (collapsed under full corpus) | 0.1351 | 0.2290 | 0.3594 | 0.5078 | 0.0358 | 0.1580 | 0.2336 | 32.42 | 566.28 | 88.10 | 198.0 |

---

## 4. Formal Acceptance Criteria & Completion Status

| Stage 3.19 Acceptance Criterion | Status | Evidentiary Artifact |
| :--- | :--- | :--- |
| **Candidate source provenance verified** | **COMPLETE** | [research/stage3_19/PRODUCTION_PARITY_AUDIT.md](file:///F:/RepoNeedle/research/stage3_19/PRODUCTION_PARITY_AUDIT.md) |
| **Production vs. research boundary explicit** | **COMPLETE** | [research/stage3_19/PRODUCTION_PARITY_AUDIT.md](file:///F:/RepoNeedle/research/stage3_19/PRODUCTION_PARITY_AUDIT.md) |
| **Clean reproduction completed** | **COMPLETE** | [research/stage3_19/CLEAN_REPRODUCTION.md](file:///F:/RepoNeedle/research/stage3_19/CLEAN_REPRODUCTION.md), [research/stage3_19/PER_QUERY_RESULTS.csv](file:///F:/RepoNeedle/research/stage3_19/PER_QUERY_RESULTS.csv) |
| **Latency methodology independently audited** | **COMPLETE** | [research/stage3_19/LATENCY_METHODOLOGY.md](file:///F:/RepoNeedle/research/stage3_19/LATENCY_METHODOLOGY.md), [research/stage3_19/LATENCY_SUMMARY.csv](file:///F:/RepoNeedle/research/stage3_19/LATENCY_SUMMARY.csv) |
| **Memory measurements use actual Process RSS** | **COMPLETE** | [research/stage3_19/MEMORY_SCALABILITY_AUDIT.md](file:///F:/RepoNeedle/research/stage3_19/MEMORY_SCALABILITY_AUDIT.md), [research/stage3_19/MEMORY_SCALABILITY.csv](file:///F:/RepoNeedle/research/stage3_19/MEMORY_SCALABILITY.csv) |
| **Statistical calculations independently reproduced** | **COMPLETE** | [research/stage3_19/STATISTICAL_AUDIT.md](file:///F:/RepoNeedle/research/stage3_19/STATISTICAL_AUDIT.md), [research/stage3_19/PAIRWISE_COMPARISONS.csv](file:///F:/RepoNeedle/research/stage3_19/PAIRWISE_COMPARISONS.csv) |
| **Historical claims reconciled & superseded** | **COMPLETE** | [research/stage3_19/CLAIM_STATUS_REGISTER.csv](file:///F:/RepoNeedle/research/stage3_19/CLAIM_STATUS_REGISTER.csv) |
| **ContextBench import readiness documented** | **COMPLETE** | [research/stage3_19/CONTEXTBENCH_IMPORT_AND_READINESS.md](file:///F:/RepoNeedle/research/stage3_19/CONTEXTBENCH_IMPORT_AND_READINESS.md) |
| **Baseline tags immutable** | **COMPLETE** | `v0.1.0-baseline` & `stage3-candidate-freeze` verified |
| **Production code untouched during audit** | **COMPLETE** | Zero lines modified under `reponeedle/` |
| **Automated test suite passing** | **COMPLETE** | [tests/test_stage3_19_production_parity_and_integrity.py](file:///F:/RepoNeedle/tests/test_stage3_19_production_parity_and_integrity.py) |
| **Formal decision verdict selected** | **COMPLETE** | **`B. INTERNALLY REPRODUCIBLE BUT NOT PRODUCTION-INTEGRATED`** |

---

## 5. Strategic Roadmap for Stage 3.20

Now that the scientific, architectural, and statistical facts are established, the next stage of RepoNeedle must focus on:
1. **Production Integration of ARM-101:** Refactor `reponeedle/core/cascade.py` and `reponeedle/engine.py` so that the default installed application executes Soft Lexical Damping ($\tau=0.25$) and verified function-call edges.
2. **Production-Parity Verification Testing:** Add end-to-end regression tests asserting that `RepoNeedleEngine.retrieve(...)` produces the exact ARM-101 ranked output on reference test queries.
3. **Out-of-Band ContextBench Ingestion:** Once network or manual transfer permits, import `full.parquet` and `contextbench_verified.parquet` to unlock the final external validation gate.
