# RepoNeedle Stage 3.14: Historical Errata & Audit Ledger

**Stage**: Stage 3.14 — Reproducibility, Historical Errata, and Independent Validation Gate  
**Date**: October 2026  
**Status**: Authoritative Historical Errata Register  
**Branch**: `research-program`  
**Base Commit**: `bf7f4c8`  

---

## 1. Executive Summary

This document establishes the authoritative historical errata register for the RepoNeedle research programme. It formally documents, catalogs, and cross-references all invalidated claims, stale metrics, synthetic artifacts, and superseded conclusions across historical stage deliverables.

In accordance with strict research integrity principles:
1. **No historical evidence is deleted or silently edited**: Historical raw data files (CSVs, JSONLs) remain immutable.
2. **Prominent warning banners have been affixed**: All historical markdown reports whose conclusions presented Candidate F as the winning architecture or cited unmeasured paper constants now display conspicuous superseding notices at the top of the file.
3. **Traceable lineage is established**: Every corrected claim links directly to its forensic audit in [`CANONICAL_LINEAGE_AUDIT.md`](file:///F:/RepoNeedle/research/stage3_13/CANONICAL_LINEAGE_AUDIT.md) and canonical metric ledgers.

---

## 2. Errata Register & Discrepancy Matrix

| Errata ID | Affected Artifact | Original Historical Claim | Corrected Empirical Reality | Root Cause & Evidence | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ERR-305-01** | [`research/stage3_5/STAGE3_5_DECISION_REPORT.md`](file:///F:/RepoNeedle/research/stage3_5/STAGE3_5_DECISION_REPORT.md) | Candidate F selected as production winner with MRR **0.2152** vs RepoMap **0.2140**. | Candidate F end-to-end MRR is **0.1334**; pinned RepoMap MRR is **0.2293**. Candidate F is invalidated. | Candidate F evaluated on Stage 2 synthetic lookups. RepoMap 0.2140 was a hardcoded paper constant. Full corpus execution caused PageRank supernode collapse. | `FORMALLY_INVALIDATED` |
| **ERR-305-02** | [`research/stage3_5/BASELINE_REPRODUCTION.md`](file:///F:/RepoNeedle/research/stage3_5/BASELINE_REPRODUCTION.md) | Candidate C baseline MRR **0.2040**, RepoMap baseline MRR **0.2140**. | True Candidate C baseline MRR is **0.1399**; true pinned RepoMap MRR is **0.2293**. | Evaluated with candidate-restricted pools and uncoupled Stage 2 lookup dictionaries rather than end-to-end full repository corpus. | `FORMALLY_SUPERSEDED` |
| **ERR-305-03** | [`research/stage3_5/FAILURE_ANALYSIS.md`](file:///F:/RepoNeedle/research/stage3_5/FAILURE_ANALYSIS.md) | Candidate F solves cross-crate polyglot disconnect with 0.2152 MRR; memory usage Click 98.6 MB, Caddy 103.1 MB. | Unpruned polyglot graph created supernodes diluting PageRank; memory measured partial corpus (Caddy 250 files vs 605 files) without CSR allocation. | Unconstrained manifest expansion added tens of thousands of dense graph edges; incomplete discovery undercounted Caddy files. | `FORMALLY_SUPERSEDED` |
| **ERR-305-04** | [`research/stage3_5/REPRODUCE.md`](file:///F:/RepoNeedle/research/stage3_5/REPRODUCE.md) | Running `evaluate_graph_retrieval.py` reproduces winning Candidate F MRR **0.2152**. | `evaluate_graph_retrieval.py` executes synthetic lookups against static paper constants; end-to-end full corpus scripts yield MRR **0.1334**. | Script decoupled retrieval from real AST generation, using precomputed dictionary targets. | `FORMALLY_SUPERSEDED` |
| **ERR-305-05** | [`research/stage3_5/EXPERIMENT_REGISTRY.jsonl`](file:///F:/RepoNeedle/research/stage3_5/EXPERIMENT_REGISTRY.jsonl) | EXP-303 (RepoMap MRR 0.2140, VERIFIED), EXP-308 (Candidate F MRR 0.2152, COMPLETED). | EXP-303 was an unmeasured constant; EXP-308 was synthetic. Pinned RepoMap is 0.2293; Candidate F is 0.1334/0.1351. | Raw registry preserved for auditability; superseded by Stage 3.8, 3.10, and 3.13 registries. | `RAW_EVIDENCE_RETAINED_HISTORICALLY_INVALIDATED` |
| **ERR-305-06** | [`research/stage3_5/GRAPH_RETRIEVAL_RESULTS.csv`](file:///F:/RepoNeedle/research/stage3_5/GRAPH_RETRIEVAL_RESULTS.csv) | Records Candidate F ARB v2 MRR 0.2078/0.2152 and RepoMap 0.2140. | Inaccurate comparison based on synthetic lookup vectors. | Superseded by canonical full-corpus per-query results in [`research/stage3_8/CANONICAL_PER_QUERY_RESULTS.csv`](file:///F:/RepoNeedle/research/stage3_8/CANONICAL_PER_QUERY_RESULTS.csv). | `RAW_EVIDENCE_RETAINED_HISTORICALLY_INVALIDATED` |
| **ERR-306-01** | [`research/stage3_6/METRIC_DISCREPANCY_TABLE.csv`](file:///F:/RepoNeedle/research/stage3_6/METRIC_DISCREPANCY_TABLE.csv) | Candidate F Token BCY@8k reported as **0.0188**. | True Candidate F Token BCY@8k is **0.1775** (or 0.2336 under skeleton packing). | Stage 3.6 evaluation script budgeted 8,000 raw characters instead of 8,000 tiktoken tokens, truncating context prematurely. | `RESOLVED_AND_CORRECTED` |
| **ERR-307-01** | [`research/stage3_7/LATENCY_MEMORY_AUDIT.md`](file:///F:/RepoNeedle/research/stage3_7/LATENCY_MEMORY_AUDIT.md) | Universal memory ceiling of 100 MB claimed across all repositories. | 100 MB ceiling violated by large repositories (Caddy requires 272.8 MB for 605 files and vocabulary CSR). | CPython runtime baseline (60-80 MB) + SciPy CSR index + vocabulary structures scale with file count. | `RESOLVED_AND_CORRECTED` |

---

## 3. Canonical Architecture Hierarchy (Post-Errata)

Following the formal invalidation of Candidate F and the correction of baseline constants:
1. **Official Baseline Reference**: Pinned official RepoMap (`9e4d689`) remains the benchmark leader on ARB v2:
   $$\text{MRR} = 0.2293, \quad \text{Recall@20} = 0.6599, \quad \text{Token BCY@8k} = 0.3177$$
2. **Canonical RepoNeedle Quality Winner**: **CONFIG-09** (Decoupled BM25 + Subword + Doc Filter $0.5\times$, No PageRank):
   $$\text{MRR} = 0.2061, \quad \text{Recall@20} = 0.5576, \quad \text{Token BCY@8k} = 0.2729$$
3. **Canonical RepoNeedle Production Optimization**: **CONFIG-10** (Sparse Cascaded Reranker with Top-50 BM25 Candidate Slicing):
   $$\text{MRR} = 0.2019, \quad \text{Recall@20} = 0.5494, \quad \text{Token BCY@8k} = 0.2633$$
   - **Equivalence Status**: Formally proven statistically equivalent to CONFIG-09 under Two One-Sided Tests (TOST) within $\Delta = \pm 0.015$ ($p = 5.12 \times 10^{-12}$).
   - **Latency Tradeoff**: $2.0\times - 3.7\times$ faster on large repositories ($\ge 600$ files); $1.1\times - 1.4\times$ slower on small repositories ($< 200$ files) due to SciPy CSR row slicing overhead.
4. **Invalidated Historical Architecture**: Candidate F (MRR 0.1334, Recall@20 0.5078) is permanently rejected and removed from production consideration.
