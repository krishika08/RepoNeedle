# REPONEEDLE STAGE 3.11: AUDIT OF RUNTIME, MEMORY & EFFICIENCY CLAIMS

**Date**: October 2026  
**Document ID**: `STAGE3.11-RUNTIME-AUDIT`  
**Git Workspace**: `F:\RepoNeedle`  
**Auditor**: Independent Performance & Retrieval Systems Auditor  

---

## 1. TIMING METHODOLOGY & BENCHMARK SETUP

This audit inspected the benchmarking harness (`research/stage3_9/audit_runtime_and_memory.py` and `research/stage3_10/CANONICAL_RESULTS.csv`):

- **Hardware Platform**: Windows 11 AMD64, Python 3.12, local SSD.
- **Timing Boundary**: Query latency measures pure retrieval call (`engine.retrieve()`), excluding repository indexing. Indexing time is measured separately.
- **Process Memory Measurement**: Windows PSAPI `K32GetProcessMemoryInfo` recording Peak Working Set Size (`WorkingSetSize` in bytes).

---

## 2. AUDIT OF UNUSUAL LATENCY OBSERVATIONS

### 2.1 The RepoMap Latency Anomaly: Identical p50 and p95 (180.20 ms)
- **Observation**: In `CANONICAL_RESULTS.csv`, RepoMap is reported with median latency of `180.20 ms` and p95 latency of `180.20 ms` ($p50 == p95$).
- **Forensic Diagnosis**: In `research/stage3_6/evaluate_systems.py` (line 307), RepoMap records were augmented with a static scalar constant:
  `"latency_ms": 180.20`
- **Audit Finding**: RepoMap was **NEVER dynamically timed per query** across the ARB benchmark in Stage 3.6–3.10. A single reference timing of 180.20 ms from prior published literature was assigned to all 345 samples.
- **Correction**: All documentation must explicitly state that RepoMap latency is a reference literature constant, not a measured per-query distribution.

### 2.2 RepoNeedle Tail Latency (p95 ~474 ms)
- **Observation**: CONFIG-09 median latency is fast ($23.20\text{ ms}$), but p95 latency rises to $474.22\text{ ms}$.
- **Root Cause**: Repository scale heterogeneity:
  - In small repositories (`pallets/click`, 136 files), query latency is $1.42\text{ ms}$.
  - In large repositories (`spring-projects/spring-boot`, 11,172 files; `huggingface/transformers`, 36 queries), computing subword dense projections across all files in pure Python requires $400\text{--}500\text{ ms}$.
- **Efficiency Mitigation**: Sparse cascaded reranking (**CONFIG-10**) filters the top-50 candidates via BM25 in $1.0\text{ ms}$ before computing subword scores, reducing large-repository latency by $40\%$ while preserving $98.0\%$ of MRR ($0.2019$ vs. $0.2061$).

---

## 3. AUDIT OF PRECISION@5 DISCREPANCY

- **Observation**: Stage 3.10 claimed RepoNeedle had a **3.9x higher Precision@5** than RepoMap ($0.0725$ vs. $0.0186$).
- **Forensic Root Cause**:
  In `external/agent-retrieval-bench/data/eval/v1_1_candidate_filter_ablation/repomap_code_only_details.jsonl`, the evaluation harness only computed:
  `dict_keys(['MRR', 'Recall@10', 'Recall@20', 'Recall@5', 'gold_coverage@8k'])`
  The key `Precision@5` was omitted from the upstream JSONL!
  When Stage 3.6 read `metrics.get("Precision@5", 0.0)`, it received `None` (defaulting to 0.0), resulting in an artificially depressed average of $0.0186$.
- **Recomputation from Raw Top-5 Files**:
  When Precision@5 is computed directly from RepoMap's actual `top_files[:5]` across all 345 queries, RepoMap's true Precision@5 is **0.0910**.
- **Audit Verdict**:
  RepoNeedle does **NOT** have higher Precision@5 than RepoMap ($0.0725$ vs. $0.0910$). The Stage 3.10 claim was an evaluation artifact caused by a missing field in an upstream file.
