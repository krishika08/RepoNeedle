# RepoNeedle Stage 3.19 — Formal Governance Decision Report

**Workspace:** `F:\RepoNeedle`  
**Branch:** `research-program`  
**Date:** 2026-10-30  
**Audit Scope:** Production Parity, Clean Reproduction, Latency Accuracy, Memory Scalability, and Statistical Rigor  
**Authoritative Verdict:** **`B. INTERNALLY REPRODUCIBLE BUT NOT PRODUCTION-INTEGRATED`**

---

## 1. Executive Summary & Core Governance Findings

Stage 3.19 was initiated to rigorously audit whether `ARM-101-BASE` is a reproducible, production-integratable retrieval architecture, and to independently verify its reported performance and efficiency claims.

### Key Audit Determinations:
1. **Candidate Reproduction:** All ARB v2 metrics for `ARM-101-BASE` (MRR $0.2078$, Recall@20 $0.5648$, Token BCY@8k $0.2822$), `BASE-BM25` (MRR $0.1752$), and `BASE-REPOMAP` (MRR $0.2293$) were reproduced bit-for-bit across all 345 positive benchmark queries without shortcuts or candidate filtering.
2. **Production Integration Boundary:** `ARM-101-BASE` does **not** exist in the production `reponeedle/` codebase. The installed package currently executes legacy router-based linear combination ($0.1399$ MRR) or pure Okapi BM25 ($0.1752$ MRR). The research champion is strictly an unintegrated prototype.
3. **Latency Timing Correction:** The historical claim of a $>13.9\times$ speedup over RepoMap was an artifact of comparing ARM-101's dynamic median ($12.92\text{ ms}$) with a static literature mean scalar ($180.20\text{ ms}$). The true mean-to-mean speedup is **$4.36\times$** ($41.30\text{ ms}$ vs $180.20\text{ ms}$).
4. **Memory Scalability:** The universal $<100\text{ MB}$ process RSS claim is definitively invalid. On complete unclipped repositories, isolated process RSS is **$198.0\text{ MB}$** on Caddy (peak $272.8\text{ MB}$) and **$364.1\text{ MB}$** on etcd (peak $609.2\text{ MB}$). Pure retained index heap is $<20\text{ MB}$, but OS runtime and matrix structures require substantial working set.
5. **Statistical Integrity:** Cluster-aware bootstrap confirms significant superiority over BM25 ($p < 0.0001$), but disproves claims of equivalence or non-inferiority to RepoMap ($p = 0.3234$, 95% CI $[-0.0741, +0.0176]$).

---

## 2. Multidimensional Leaderboard & Trade-off Differentiation

In accordance with strict research governance, candidates are evaluated across distinct engineering and retrieval dimensions rather than collapsed into an oversimplified "winner" label:

| Candidate Architecture | Best Dimension | ARB v2 MRR | Recall@20 | Token BCY@8k | P50 Query Latency | Isolated Process RSS | Production Parity |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **BASE-REPOMAP** (9e4d689) | **Best Raw Retrieval Quality** | **0.2293** | **0.6599** | **0.3177** | 180.20 ms* | 198.0 MB | External Reference |
| **ARM-101-BASE** (Prototype) | **Best Speed/Quality Trade-off** | 0.2078 | 0.5648 | 0.2822 | 12.92 ms | 198.0 MB | **0% (Unintegrated)** |
| **BASE-BM25** (Okapi BM25) | **Best Raw Query Latency** | 0.1752 | 0.4535 | 0.2150 | **10.24 ms** | **112.7 MB** | 100% (Production) |
| **CONTROL-CASCADE** (Cascade) | Intermediate Lexical Freeze | 0.1897 | 0.5217 | 0.2540 | 13.11 ms | 198.0 MB | Available (Unused) |
| **CAND-C** (Legacy Fusion) | Baseline / Legacy Default | 0.1399 | 0.5105 | 0.2410 | 28.50 ms | 198.0 MB | Current Default |

*Deployment Guidance:*
- If maximizing raw top-k accuracy without concern for indexing latency is the sole priority, **RepoMap** remains superior.
- If interactive CPU-first agent speed ($\le 15\text{ ms}$ query latency) with high token yield is required, **ARM-101** is the superior algorithmic architecture—**provided it is actually ported into production.**

---

## 3. Formal Four-Option Verdict Selection

The Stage 3.19 specification mandated selecting one of four preregistered verdicts based strictly on completed empirical evidence:

- [ ] **A. INTERNALLY REPRODUCIBLE AND PRODUCTION-PARITY VERIFIED**  
  *Rejected:* Although internally reproducible, ARM-101 has zero production code presence under `reponeedle/`.
- [x] **B. INTERNALLY REPRODUCIBLE BUT NOT PRODUCTION-INTEGRATED**  
  *Selected:* The $0.2078$ MRR metrics reproduce cleanly and deterministically across all 345 queries, but the algorithm exists solely in `research/` scripts and is not executed by the production package.
- [ ] **C. REPRODUCTION INCOMPLETE**  
  *Rejected:* Reproduction was 100% complete across all 345 positive benchmark queries and 218 snapshots.
- [ ] **D. EVIDENCE INCONSISTENT**  
  *Rejected:* Metric discrepancies and latency anomalies were fully explained, mathematically modeled, and resolved.

---

## 4. Mandatory Stage 3.20 Action Items

Before any further external claims or publishing:
1. **Production Integration Gate:** Migrate `ARM-101` (Soft Lexical Damping $\tau=0.25$, verified call edges, and package fencing) into `reponeedle/core/cascade.py` and connect it as the default retrieve execution path in `reponeedle/engine.py`.
2. **Production Parity Unit Tests:** Implement automated regression tests verifying that `RepoNeedleEngine.retrieve(...)` produces the exact ARM-101 ranking on benchmark reference queries.
3. **External Benchmark Gate Maintenance:** Maintain the ContextBench gate as `BLOCKED — OFFICIAL DATA ACQUISITION` until verified upstream parquet files are acquired without security bypasses.
