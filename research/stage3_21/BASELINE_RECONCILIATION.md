# Baseline Comparisons & RepoMap Provenance Reconciliation

**Date:** 2026-10-30  
**Stage:** 3.21  
**Experiment ID:** `EXP-321-03`  
**Status:** RECONCILED & AUTHORITATIVE  

---

## 1. Executive Summary

Phase 3 establishes an authoritative baseline reconciliation across all candidate architectures evaluated on the canonical ARB v2 benchmark (345 positive queries, 218 snapshots). It resolves the historical variance in reported RepoMap figures and strictly enforces methodological hygiene: **external literature figures must never be combined or directly compared with local empirical measurements.**

---

## 2. Forensic Reconciliation of RepoMap Historical Figures

Across the research archive, multiple figures have been cited for upstream RepoMap. Forensic analysis resolves the exact origin of each figure:

| Reported Figure | Historical Stage | Context / Metric | Forensic Origin & Status |
| :--- | :---: | :--- | :--- |
| **`0.2140`** | Stage 3.5, 3.6, 3.7 | "RepoMap MRR" | **SUPERSEDED HARDCODED CONSTANT**: Early preliminary estimate computed on a restricted or clamped corpus (e.g. Caddy clamped to 250 files). Registered in Stage 3.19 claim register as `CLM-003`. |
| **`0.2293`** | Stage 3.10–3.20 | "RepoMap MRR" | **AUTHORITATIVE CANONICAL MRR**: Full unconstrained evaluation of official upstream Aider commit `9e4d689` across all 345 positive queries on 218 full snapshots. |
| **`0.6599`** | Stage 3.10, 3.11 | "RepoMap Performance" | **RECALL@20**: Not MRR! In Stage 3.10, RepoMap achieved Recall@20 of 0.6599 ($227.67 / 345$). Mistakenly cited in some notes as general retrieval accuracy. |
| **`0.1334`** | Stage 3.10.1, 3.16 | "RepoMap Precision" | **TOP-1 HIT RATE (Hit@1)**: Fraction of queries where the true target was at Rank #1. |
| **`180.20 ms`** | Stage 3.14, 3.15 | "RepoMap Latency" | **EXTERNAL LITERATURE MEAN SCALAR**: Single static mean scalar published in upstream Aider evaluation documentation on Linux server hardware. Erroneously copied across P50, P90, P95, and P99 percentiles in early stages. |

### Methodological Rule on Latency Comparison
RepoMap's `180.20 ms` latency was measured in an external Linux execution environment with native tree-sitter C bindings and different CPU specifications. RepoNeedle's query latencies are measured locally using Python `time.perf_counter()` on Windows 11.
**Strict Governance Directive:** RepoMap is classified as an **External Literature Reference**. Its published 180.20 ms latency cannot be used to claim an empirical speedup ratio (e.g., "13.9x faster") against RepoNeedle's local median latency.

---

## 3. Matched Local vs. External Leaderboard Matrix

All local candidates were executed on the same hardware environment under the identical harness and evaluation contract:

| Candidate ID | Execution Type | Implementation / Source | MRR | Recall@5 | Recall@10 | Recall@20 | Precision@20 | P50 Latency (ms) | Mean Latency (ms) | Peak Process RSS (MB) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ARM-101-PROD** | **Matched Local** | `reponeedle --ranker arm101` (commit `0b8ce84`) | **0.2078** | **0.3391** | **0.4493** | **0.5648** | **0.0397** | 12.92 | 41.30 | 198.0 (Caddy) / 286.7 (etcd) |
| **CONTROL-CASCADE-PROD** | **Matched Local** | `reponeedle --ranker cascade` (commit `0b8ce84`) | 0.1897 | 0.3120 | 0.4180 | 0.5217 | 0.0368 | 13.11 | 42.74 | 198.0 (Caddy) / 286.7 (etcd) |
| **BASE-BM25-PROD** | **Matched Local** | `reponeedle --ranker bm25` (commit `0b8ce84`) | 0.1752 | 0.2928 | 0.3942 | 0.4535 | 0.0322 | **10.24** | **36.29** | 149.9 (Caddy) / 198.5 (etcd) |
| **LEGACY-FUSION-PROD** | **Matched Local** | `reponeedle --ranker legacy` (commit `0b8ce84`) | 0.1399 | 0.2319 | 0.3623 | 0.5105 | 0.0355 | 28.50 | 78.20 | 198.0 (Caddy) / 286.7 (etcd) |
| **BASE-REPOMAP** | **External Reference** | Upstream Aider `9e4d689` (literature reference) | **0.2293** | **0.3855** | **0.5275** | **0.6599** | **0.0462** | 180.20* | 180.20* | 198.0* |

*\*Note: Marked with asterisk to denote external literature values that are not directly comparable to matched local measurements.*

Complete per-candidate configuration and metrics are exported to [research/stage3_21/BASELINE_COMPARISON.csv](file:///F:/RepoNeedle/research/stage3_21/BASELINE_COMPARISON.csv).
