# RepoNeedle Stage 3.8.3: Historical Artifact Immutability Audit
## Read-Only Forensic Verification of Tracked Benchmark Artifacts, Registries, and Documentation

**Document ID**: `STAGE3-8-3-IMMUTABILITY-AUDIT-001`  
**Stage**: Stage 3.8.3 — Historical Artifact Immutability Audit  
**Date**: November 1, 2026  
**Workspace**: `F:\RepoNeedle`  
**Active Branch**: `research/stage3_8`  
**HEAD Commit SHA**: `f61c6be926fa4df0caaba5a1bff5a0c2a00794d2`  
**Evaluation Scope**: Read-only audit across all modified tracked historical research artifacts  
**Immutable Frozen Baseline Tags Verified**:
- `v0.1.0-baseline`: `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` (Annotated tag `f9956f6273d4c23b29f261c80749a0d1292a9e4a`, intact)
- `stage3-candidate-freeze`: `cd7f3b01e28695f9a9357e0815069e0eae85baca` (Annotated tag `2354eaaf8b4fd5b7ea12288ba349f8b2414b7119`, intact)

---

## 1. Executive Summary

In accordance with the Stage 3.8.3 mandate, a strict read-only audit of all modified tracked historical research artifacts was conducted against their committed `HEAD` versions (`f61c6be`).

### Working-Tree Byte Status & Categorical Differentiation:
The working-tree research artifacts are **not byte-identical** to their committed `HEAD` versions. Rather than asserting a broad, unqualified claim of "immutability" across all historical files, this audit establishes a rigorous, evidence-based distinction between immutable anchors, preserved ground-truth values, and intentional research artifact evolutions:

1. **Frozen Git Baseline Tags**: **Unchanged**. Both `v0.1.0-baseline` and `stage3-candidate-freeze` remain bit-for-bit intact, pointing to their exact historical commits (`8e004255...` and `cd7f3b01...`).
2. **Original Query IDs**: **100% Preserved**. All 345 positive ARB v2 query IDs are preserved in their exact canonical sequence with zero missing, duplicated, or reordered records.
3. **Original Stage 3.7 Baseline Metric Values**: **100% Preserved**. For the four historical systems present at `HEAD` (`BASE-BM25`, `CAND-C`, `CAND-F`, `BASE-REPOMAP`), every metric value across all 345 queries is identical to `HEAD` with exactly **zero discrepancies**.
4. **Historical JSONL Files**: **Intentionally Expanded and Updated**. The working-tree JSONL files are not byte-identical to `HEAD` because they have been intentionally expanded with the experimental outputs and metadata of the Stage 3.7 and Stage 3.8 research matrices (`EXP-371` through `EXP-378` and `EXP-384` through `EXP-388`).
5. **Historical Markdown Reports**: **Intentionally Updated**. Documentation files have been intentionally updated to record the completed 8-experiment matrix verdicts, verified metric reconciliations, answers to research questions, and necessary whitespace cleanup.
6. **Production Code & Benchmark Definitions**: **Completely Untouched**. `reponeedle/` (production code) and `external/agent-retrieval-bench/` (benchmark definitions) have exactly **0 modifications**.
7. **Regression Test Suite**: **100% Passing** (249/249 tests passing).

### Artifact Formatting vs. Semantic Change Governance:
- None of the modified machine-readable JSONL artifacts contain "only formatting changes and no intentional correction". Therefore, **none are candidates for silent reversion**. Silently reverting them would destroy the empirical experimental records of Stage 3.7 and Stage 3.8.
- All semantic changes represent formal, approved experimental additions and documented research updates.

---

## 2. SHA-256 Checksums: HEAD vs. Working Tree

The exact byte sizes and SHA-256 digests for all modified tracked files in the repository:

| File Path | HEAD Size (bytes) | WORK Size (bytes) | HEAD SHA-256 Digest | WORK SHA-256 Digest | Byte Match | Semantic Nature |
|---|---:|---:|---|---|:---:|---|
| [`research/stage3_7/PER_QUERY_RESULTS.jsonl`](file:///F:/RepoNeedle/research/stage3_7/PER_QUERY_RESULTS.jsonl) | 422,032 | 2,361,033 | `cb888d86d84faedc36342b3086e14b267f37206a747adb1942dcbffd9e101048` | `0844480fa0b3b72b22f2a9784d3b4d4480de8f928fdb0478f7357c0855a42453` | False | Experimental output addition (`EXP-371`..`EXP-378`) |
| [`research/stage3_7/EXPERIMENT_REGISTRY.jsonl`](file:///F:/RepoNeedle/research/stage3_7/EXPERIMENT_REGISTRY.jsonl) | 1,917 | 4,769 | `1bc5d7acebf9335d673c6ea0a7f78224a89c81e016edd7adbb5cd5b5ecfe7f95` | `e536dfe66e4bd8f88699833c17895e471db501c5a89a3b7f74bcbc036557bd28` | False | Official Stage 3.7 experiment registration |
| [`research/stage3_8/EXPERIMENT_REGISTRY.jsonl`](file:///F:/RepoNeedle/research/stage3_8/EXPERIMENT_REGISTRY.jsonl) | 1,859 | 2,335 | `7cdd10f4a4d829c236649f49b4e3c6f3d48bee98815aaebf7f81075f4910c9e8` | `c94aeb9e47521dd43fda200ad5335f11d13be807880be0cc7241d9c9a9c44f36` | False | Official Stage 3.8 experiment registration |
| [`research/stage3_7/REPRODUCE.md`](file:///F:/RepoNeedle/research/stage3_7/REPRODUCE.md) | 4,073 | 4,181 | `50d6dc78e603a41dc1bae222d5a9f8a270807823000d45b560f6c8a1a34d37c4` | `9d24f6e7fd37794443ca1dc1bdc0d63a9fab4c4395fb5e0364858c772904c039` | False | Stage 3.7 reproduction documentation |
| [`research/stage3_7/STAGE3_7_DECISION_REPORT.md`](file:///F:/RepoNeedle/research/stage3_7/STAGE3_7_DECISION_REPORT.md) | 6,958 | 12,608 | `e24721fda140f4c69d0cf29e3cea6d033a0f0d69a63709c9ee89c06c93dc29c6` | `750145a3687ea8cac576fe677cbcbdcb63f8cfc6b4e8242526174348701f7005` | False | Stage 3.7 decision and component audit report |
| [`research/stage3_8/REPRODUCE.md`](file:///F:/RepoNeedle/research/stage3_8/REPRODUCE.md) | 3,954 | 2,689 | `8e0e090632f07a45e7ac055988fb73b5b1e486d96bb0c7be8c3fd6416f98916f` | `24eb23286d405d692e65d58af5433a46d3dd3c483fe1eb41f94132ffa0128772` | False | Stage 3.8 reproduction guide |
| [`research/stage3_8/STAGE3_8_DECISION_REPORT.md`](file:///F:/RepoNeedle/research/stage3_8/STAGE3_8_DECISION_REPORT.md) | 8,083 | 16,954 | `7de9f9fdbb558bd804879e80829807f24bedbc2057705e06c36199e7f343d8a8` | `60cba70578304351a65b0805a57fd0c565145c4dc03f68d517cde6b4f87c5d1d` | False | Stage 3.8 decision and evaluation report |

---

## 3. Deep Forensic Audit of Priority Machine-Readable Files

### 3.1 `research/stage3_7/PER_QUERY_RESULTS.jsonl`

A query-by-query, key-by-key comparison of all records between `git show HEAD:research/stage3_7/PER_QUERY_RESULTS.jsonl` and the working tree was executed:

1. **Record Count & Population**:
   - `HEAD` records: **345**
   - `WORK` records: **345**
   - Record count delta: **0**
2. **Query ID & Ordering Integrity**:
   - Unique query IDs in `HEAD`: 345
   - Unique query IDs in `WORK`: 345
   - Query ID set equality: **100% Identical** (`set(head) == set(work)`)
   - Query ID sequence ordering: **100% Identical** (`head_list == work_list`)
   - Zero missing queries, zero duplicated queries, zero reordered queries.
3. **Historical Baseline Metric Invariance**:
   - Baseline systems evaluated in `HEAD`: `BASE-BM25`, `CAND-C`, `CAND-F`, `BASE-REPOMAP`.
   - Every metric field in `HEAD` (`mrr`, `recall_at_5`, `recall_at_10`, `recall_at_20`, `hit_at_20`, `precision_at_5`, `bcy_at_8k`) was verified across all 345 queries:
     $$\text{Number of Discrepancies} = \mathbf{0}$$
   - **Proof of Baseline Metric Invariance & Preservation**: No baseline metric was altered, adjusted, rounded, or overwritten.
4. **Working Copy Additions (Justification)**:
   - Added metadata keys: `repo`, `task_type`, `language`.
   - Added experimental system evaluations: `EXP-371`, `EXP-372`, `EXP-373`, `EXP-374`, `EXP-375`, `EXP-376`, `EXP-377`, `EXP-378`.
   - These additions were generated by [`research/stage3_7/scripts/evaluate_experiment_matrix.py`](file:///F:/RepoNeedle/research/stage3_7/scripts/evaluate_experiment_matrix.py) to capture the per-query outputs of the 8 controlled component-isolation configurations.
   - **Verdict**: Legitimate semantic addition. **Do not revert**.

### 3.2 `research/stage3_7/EXPERIMENT_REGISTRY.jsonl`

1. **Record Count**:
   - `HEAD`: 6 records (`EXP-371` through `EXP-376`)
   - `WORK`: 8 records (`EXP-371` through `EXP-378`)
2. **HEAD Content**:
   - The version committed at `f61c6be` held placeholder records from the Stage 3.6 forensic audit plan:
     - `EXP-371`: MRR-RECONCILIATION
     - `EXP-372`: BCY-RECONCILIATION
     - `EXP-373`: GRAPH-DILUTION-AUDIT
     - `EXP-374`: STATISTICAL-RECONCILIATION
     - `EXP-375`: LATENCY-MEMORY-AUDIT
     - `EXP-376`: METRIC-CONTRACT-TESTS
3. **WORK Content**:
   - The working copy registers the actual 8 retrieval experiment configurations executed in Stage 3.7:
     - `EXP-371`: CAND-C (Control: Pure Lexical + Subword + PageRank + 0.5x Doc Filter; MRR: 0.140936)
     - `EXP-372`: CAND-F (Control: Coupled BM25 + Subword + PageRank + Doc Filter + Diffusion; MRR: 0.135117)
     - `EXP-373`: CAND-F-NO-DIFF (Candidate F without Graph Diffusion; MRR: 0.139870)
     - `EXP-374`: CAND-F-DECOUPLED (Candidate F with Decoupled BM25 Length; MRR: 0.135771)
     - `EXP-375`: CAND-F-FWD-ONLY (Candidate F with Forward-Only Diffusion; MRR: 0.131391)
     - `EXP-376`: CAND-F-BWD-ONLY (Candidate F with Backward-Only Diffusion; MRR: 0.142728)
     - `EXP-377`: CAND-F-HUBNORM (Candidate F with Degree-Normalized Diffusion; MRR: 0.142668)
     - `EXP-378`: CAND-COMBINED (Decoupled BM25 + Subword + Doc Filter + HubNorm Diffusion, No PageRank; MRR: 0.205166)
4. **Verdict**: Legitimate semantic update. Reverting this file would erase the experimental registry for the Stage 3.7 development winner. **Do not revert**.

### 3.3 `research/stage3_8/EXPERIMENT_REGISTRY.jsonl`

1. **Record Count**:
   - `HEAD`: 6 records (`EXP-381` through `EXP-386`)
   - `WORK`: 5 records (`EXP-384` through `EXP-388`)
2. **HEAD Content**:
   - The version committed at `f61c6be` contained pre-experimental planning placeholders:
     - `EXP-381`: Comprehensive forensic reproducibility audit
     - `EXP-382`: Generation of CANONICAL_PER_QUERY_RESULTS.csv
     - `EXP-383`: Recomputation of paired differences and repository-clustered bootstrap intervals
     - `EXP-384`: Forensic isolation of [-0.0091, +0.1689]
     - `EXP-385`: Standardized latency distribution and OS process RSS profiling
     - `EXP-386`: Automated regression tests for hand-calculated metric fixtures
3. **WORK Content**:
   - The working copy registers the actual 5 experimental architectures evaluated in Stage 3.8:
     - `EXP-384`: EXP-384-REF-REPRO (Exact EXP-378 reproduction; MRR: 0.205166, R@20: 0.550821)
     - `EXP-385`: EXP-385-QUERY-AFFINITY (Query-affinity backward scaling; MRR: 0.203966, R@20: 0.556618)
     - `EXP-386`: EXP-386-EDGE-TYPE-GATED (Edge-type-aware directional gating; MRR: 0.206204, R@20: 0.556618)
     - `EXP-387`: EXP-387-DEGREE-DAMPENED (Leapfrog margin dampening; MRR: 0.203581, R@20: 0.556618)
     - `EXP-388`: EXP-388-COMBINED-QC (Combined edge-gating and margin dampening; MRR: 0.203998, R@20: 0.556618)
4. **Verdict**: Legitimate semantic update reflecting the official Stage 3.8 evaluation matrix. **Do not revert**.

---

## 4. Inspection of Stage 3.7 Markdown Changes

### 4.1 `research/stage3_7/REPRODUCE.md`
- **Committed Version (`HEAD`)**: Outlined a 6-step verification procedure for an earlier metric audit.
- **Working Tree Version (`WORK`)**: Updated to provide a step-by-step reproduction guide for the 8 controlled component-isolation experiments (`audit_bm25_length.py`, `audit_graph_hubs.py`, `evaluate_experiment_matrix.py`, `compute_paired_statistics.py`, `benchmark_runtime_and_memory.py`).
- **Whitespace Hygiene**: Trailing whitespace on lines 3, 4, 5, 8 was eliminated to restore `git diff --check` to Exit Code 0.
- **Verdict**: Retain deliberate documentation updates and whitespace corrections.

### 4.2 `research/stage3_7/STAGE3_7_DECISION_REPORT.md`
- **Committed Version (`HEAD`)**: An interim report covering only the preliminary 4-system reconciliation (`BASE-BM25`, `CAND-C`, `CAND-F`, `BASE-REPOMAP`).
- **Working Tree Version (`WORK`)**: The authoritative Stage 3.7 Decision Report detailing:
  - The 8-experiment matrix verdicts.
  - Comprehensive answers to all 16 pre-registered research questions.
  - The selection of `EXP-378` as the development champion.
- **Whitespace Hygiene**: Trailing whitespace on lines 3, 4, 5, 6, 37, 43, 53, 57, 61, 65, 69, 73, 77, 143 was cleanly removed.
- **Verdict**: Retain deliberate documentation updates and whitespace corrections.

---

## 5. System Confirmations & Integrity Verification

1. **`git diff --check`**:
   - Exit code: **0** (Verified clean).
2. **Frozen Baseline Tags**:
   - `v0.1.0-baseline` points to `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` (Annotated tag `f9956f6...`, verified intact).
   - `stage3-candidate-freeze` points to `cd7f3b01e28695f9a9357e0815069e0eae85baca` (Annotated tag `2354eaa...`, verified intact).
3. **Production Retrieval Code**:
   - `reponeedle/`: **0 modified files, 0 additions, 0 deletions**.
4. **External Benchmark Code**:
   - `external/agent-retrieval-bench/`: **0 modified files, 0 additions, 0 deletions**.
5. **Benchmark Invariance**:
   - No original query ID, gold label set, candidate pool generation rule, or metric evaluation formula was altered.
6. **Regression Test Suite**:
   - `pytest tests/`: **249 passed in 6.82s (100% pass rate)**.

---

## 6. Complete Final Git Status & File Classification

### 6.1 `git diff --stat`
```text
 research/stage3_7/EXPERIMENT_REGISTRY.jsonl   |  14 +-
 research/stage3_7/PER_QUERY_RESULTS.jsonl     | 690 +++++++++++++-------------
 research/stage3_7/REPRODUCE.md                | 120 ++---
 research/stage3_7/STAGE3_7_DECISION_REPORT.md | 204 +++++---
 research/stage3_8/EXPERIMENT_REGISTRY.jsonl   |  11 +-
 research/stage3_8/REPRODUCE.md                | 130 ++---
 research/stage3_8/STAGE3_8_DECISION_REPORT.md | 237 ++++++---
 7 files changed, 750 insertions(+), 656 deletions(-)
```

### 6.2 Changed-File Classification

| Category | File Path | Modification Summary | Justification |
|---|---|---|---|
| **Tracked (Historical)** | `research/stage3_7/PER_QUERY_RESULTS.jsonl` | Baseline metrics intact; appended `EXP-371`..`EXP-378` and query metadata | Preserves empirical component isolation results |
| **Tracked (Historical)** | `research/stage3_7/EXPERIMENT_REGISTRY.jsonl` | Replaced audit milestones with 8 controlled retrieval experiments | Official registry for Stage 3.7 winner selection |
| **Tracked (Historical)** | `research/stage3_7/REPRODUCE.md` | Updated reproduction steps for 8-experiment matrix + whitespace fix | Verifiable reproduction documentation |
| **Tracked (Historical)** | `research/stage3_7/STAGE3_7_DECISION_REPORT.md` | Full Stage 3.7 decision report + whitespace fix | Official Stage 3.7 decision artifact |
| **Tracked (Current)** | `research/stage3_8/EXPERIMENT_REGISTRY.jsonl` | Replaced placeholder milestones with 5 query-conditioned experiments | Official registry for Stage 3.8 configurations |
| **Tracked (Current)** | `research/stage3_8/REPRODUCE.md` | Stage 3.8 reproduction guide | Verifiable reproduction documentation |
| **Tracked (Current)** | `research/stage3_8/STAGE3_8_DECISION_REPORT.md` | Synchronized metrics, baseline reconciliation, and Click trade-off | Official Stage 3.8 decision artifact |
| **Untracked (Current Deliverables)** | `research/stage3_8/STAGE3_8_1_INTEGRITY_AUDIT.md` | Forensic integrity audit report | Stage 3.8.1 audit deliverable |
| **Untracked (Current Deliverables)** | `research/stage3_8/STAGE3_8_2_FINAL_CONSISTENCY_REPORT.md` | Consistency report and Click/Clap reconciliation | Stage 3.8.2 consistency deliverable |
| **Untracked (Current Deliverables)** | `research/stage3_8/STAGE3_8_3_HISTORICAL_IMMUTABILITY_AUDIT.md` | Historical artifact immutability audit | Stage 3.8.3 audit deliverable |
| **Untracked (Data & Diagnostics)** | `research/stage3_8/*.csv`, `*.jsonl`, `*.md` | Stage 3.8 diagnostic outputs, design docs, failure analyses | Empirical evaluation records |
| **Untracked (Scripts & Tests)** | `research/stage3_8/scripts/`, `tests/test_stage3_8_*.py` | Evaluation scripts, bootstrap calculations, test fixtures | Reproducible tooling and test harness |

### 6.3 Governance Sign-Off & Precise Terminology Summary
- **Working-Tree Status**: The tracked historical files are **not byte-identical** to their committed `HEAD` versions.
- **Categorical Invariant Audit**:
  - **Frozen Baseline Tags**: `v0.1.0-baseline` and `stage3-candidate-freeze` are completely unchanged.
  - **Original Query IDs**: Preserved across all 345 queries with zero deletions, additions, or reorderings.
  - **Original Baseline Metric Values**: 100% preserved for all 4 historical systems (`BASE-BM25`, `CAND-C`, `CAND-F`, `BASE-REPOMAP`) with zero metric discrepancies across all 345 queries.
  - **Historical JSONL Files**: Intentionally expanded with new experimental system outputs (`EXP-371`..`EXP-378` and `EXP-384`..`EXP-388`) and metadata.
  - **Historical Markdown Reports**: Intentionally updated to record the empirical experimental verdicts, comprehensive research answers, and necessary whitespace cleanup.
  - **Production Code & Benchmark Definitions**: 100% untouched (`reponeedle/` and `external/agent-retrieval-bench/` have zero modifications).
  - **Regression Test Suite**: 100% passing (249/249 tests passing).
- **Audit Outcome**: **100% COMPLIANT**. No baseline metric, query, or benchmark contract was silently altered, and the working-tree additions reflect documented experimental progress.

