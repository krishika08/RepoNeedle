# ARB v2 Task-Count Forensic Reconciliation & Population Manifest

**Date:** 2026-10-30  
**Stage:** 3.21  
**Experiment ID:** `EXP-321-01`  
**Status:** RECONCILED & AUTHORITATIVE  

---

## 1. Executive Summary

In Stage 3.20, the narrative report ([research/stage3_20/STAGE3_20_REPORT.md](file:///F:/RepoNeedle/research/stage3_20/STAGE3_20_REPORT.md), lines 101–104) reported the following task-level breakdown for the 345-query ARB v2 development benchmark:
- `code2test`: 70 queries
- `edit2ripple`: 92 queries
- `comment2context`: 113 queries
- `trace2code`: 70 queries
- **Total:** 345 queries

This distribution conflicted with the historical literature across all previous stages (Stages 1 through 3.19), which consistently documented:
- `code2test`: 106 queries
- `comment2context`: 80 queries
- `trace2code`: 101 queries
- `edit2ripple`: 58 queries
- **Total:** 345 queries

Phase 1 conducted a forensic investigation across the raw source data in `external/agent-retrieval-bench`, all intermediate stage result CSVs, and previous audit reports to determine the exact origin of this discrepancy.

---

## 2. Forensic Findings & Root Cause Analysis

### 2.1 Raw Dataset Source & Pinned Commit
- **Repository:** `external/agent-retrieval-bench`
- **Branch:** `main`
- **Git Commit SHA:** `9e4d68937f29d5967afd62f4f6a24c1478298133`
- **Corpus Manifest:** `external/agent-retrieval-bench/data/corpus/v2_selective_mixed/corpus_manifest.jsonl` (218 repository snapshots across 25 repositories)
- **Benchmark Sample Files:**
  - `data/benchmark/v2_code2test/samples.jsonl`: **106** samples
  - `data/benchmark/v2_comment2context/samples.jsonl`: **80** samples
  - `data/benchmark/v2_trace2code/samples.jsonl`: **101** samples
  - `data/benchmark/v2_edit2ripple/samples.jsonl`: **58** samples
  - **Raw Sum:** $106 + 80 + 101 + 58 = \mathbf{345}$ samples.

### 2.2 Recomputation from Underlying Stage 3.20 Data
An inspection of the actual data produced and evaluated in Stage 3.20 demonstrates that the underlying experiment evaluated the exact canonical 345 queries:
- [research/stage3_20/PRODUCTION_PER_QUERY_RESULTS.csv](file:///F:/RepoNeedle/research/stage3_20/PRODUCTION_PER_QUERY_RESULTS.csv):
  - `code2test`: 106 queries (mean ARM-101 MRR = 0.1257)
  - `comment2context`: 80 queries (mean ARM-101 MRR = 0.1984)
  - `edit2ripple`: 58 queries (mean ARM-101 MRR = 0.2654)
  - `trace2code`: 101 queries (mean ARM-101 MRR = 0.2683)
  - **Overall Weighted Mean MRR:**
    $$\frac{106 \times 0.125713 + 80 \times 0.198440 + 58 \times 0.265415 + 101 \times 0.268311}{345} = \mathbf{0.207802}$$

- [research/stage3_19/PER_QUERY_RESULTS.csv](file:///F:/RepoNeedle/research/stage3_19/PER_QUERY_RESULTS.csv):
  - Contains the identical 345 queries with matching per-task counts: 106, 80, 58, 101.

- [research/stage3_20/CANDIDATE_F_METRIC_RECOMPUTATION.csv](file:///F:/RepoNeedle/research/stage3_20/CANDIDATE_F_METRIC_RECOMPUTATION.csv):
  - Evaluated Candidate F on 106 `code2test`, 80 `comment2context`, 58 `edit2ripple`, and 101 `trace2code` queries.

### 2.3 The Root Cause of the Discrepancy
The discrepancy was **not** caused by a change in benchmark data, a missing filter, or an altered dataset version.
It was a **purely clerical transcription error** introduced exclusively in the narrative prose of `research/stage3_20/STAGE3_20_REPORT.md` (lines 101–104). The numbers (70, 92, 113, 70) were artificially constructed in prose to sum to 345 and yield an average near 0.2078 ($71.65 / 345 = 0.20768$), but they never existed in any data file, script, or evaluation output.

---

## 3. Authoritative Task Distribution & Cross-Stage Matrix

| Workflow Task | Raw Files (`samples.jsonl`) | Stage 1–3.19 Historical Reports | Stage 3.20 Data (`PRODUCTION_PER_QUERY_RESULTS.csv`) | Stage 3.20 Narrative Error (`STAGE3_20_REPORT.md`) | Authoritative Stage 3.21 Definition |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `code2test` | 106 | 106 | 106 | 70 *(error)* | **106** |
| `comment2context` | 80 | 80 | 80 | 113 *(error)* | **80** |
| `trace2code` | 101 | 101 | 101 | 70 *(error)* | **101** |
| `edit2ripple` | 58 | 58 | 58 | 92 *(error)* | **58** |
| **Total** | **345** | **345** | **345** | **345** | **345** |

---

## 4. Manifest Export & Cryptographic Verification

The canonical population of all 345 positive evaluation queries has been exported to [research/stage3_21/ARB_QUERY_MANIFEST.csv](file:///F:/RepoNeedle/research/stage3_21/ARB_QUERY_MANIFEST.csv).

- **Total Queries:** 345
- **Unique Query IDs:** 345 (Zero duplicates, zero omissions)
- **Repository Snapshots:** 218 unique `(repository, base_commit)` tuples across 25 repositories
- **SHA256 Checksum of Manifest:** Verified in starting source hashes.
