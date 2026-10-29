# RepoNeedle Stage 3.12A: Evaluator Differences and Metric Discrepancy Reconciliation

**Document**: `research/stage3_12a/EVALUATOR_DIFFERENCES.md`  
**Stage**: Stage 3.12A — Canonical Evaluation Reconciliation and Graph Research Gate  
**Date**: October 29, 2026  

---

## 1. Discrepancy Overview

The reported metrics between Stage 3.5 and Stage 3.11 exhibit material divergences:

| Metric | Stage 3.5 Reported | Stage 3.11 Canonical | Direct Delta | Audit Characterization |
| :--- | :---: | :---: | :---: | :--- |
| **Candidate F MRR** | 0.2152 | 0.1338 (Recomputed) | $-0.0814$ | Candidate Pool Leakage & Synthetic Ripgrep Fixture |
| **RepoMap MRR** | 0.2140 | 0.2293 | $+0.0153$ | Hardcoded Reference Constant vs. Live Run |
| **Candidate F Recall@20** | 0.5652 | 0.5078 (Recomputed) | $-0.0574$ | Binary Hit Rate Mislabeled as Fractional Recall |
| **RepoMap Recall@20** | 0.5681 / 0.6306 | 0.6599 | $+0.0918$ | Binary Hit Rate Substitution vs. True Fractional Recall |
| **RepoNeedle Best MRR** | 0.2152 (`CAND-F`) | 0.2082 (`FUNCTION-GRAPH-NO-FREEZE`) / 0.1901 (`FUNCTION-GRAPH`) | $-0.0070$ / $-0.0251$ | Valid Dynamic Fusion vs. Invalid Filtered Fixture |

This document addresses all 10 forensic checkpoints to explain every numerical discrepancy.

---

## 2. Forensic Investigation of the 10 Evaluation Checkpoints

### 2.1 Evaluated Query IDs and Positive Denominator ($N = 345$)
- Both Stage 3.5 and Stage 3.11 evaluated across the identical 4 ARB v2 positive benchmark subsets:
  - `code2test`: 106 queries (Stage 3.5 originally reported 75 in v0.1 format, updated to 106 in v2).
  - `comment2context`: 80 queries.
  - `trace2code`: 101 queries (formerly 90 in v0.1 format).
  - `edit2ripple`: 58 queries (formerly 100 in v0.1 format).
- **Audit Finding**: In both Stage 3.5 and Stage 3.11, the total positive query denominator evaluated across all subsets was exactly **$N = 345$ queries**. No queries were dropped, excluded, or duplicated.

### 2.2 Query Alignment and Consistency
- Query ID matching was verified row-for-row between Stage 3.5 lookup keys, Stage 3.10.2 canonical keys, and Stage 3.11 keys.
- **Audit Finding**: The 345 query IDs are identical across all stages. The discrepancy is **not** caused by query sampling, split variance, or missing IDs.

### 2.3 Failed Queries and Exception Handling
- In Stage 3.5, if a query encountered an indexing failure or missing snapshot, it fell back to a default score dictionary (`m_bm25 = {"mrr": 0.1705, ...}`).
- In Stage 3.10.2 and Stage 3.11, all 218 positive snapshots are verified present on local disk in `external/agent-retrieval-bench/data/corpus/v2_selective_mixed/`; 100% of queries executed with zero exceptions.

### 2.4 Candidate Pool Universe Construction
- **Stage 3.5**: In the `code2test` task, the evaluation harness invoked `filter_candidate_chunks(chunks, candidate_filter="tests_only")`, artificially pruning out all non-test files from the candidate pool before scoring. For a repository with 500 files and 15 test files, the retriever only ranked among 15 files, artificially inflating reciprocal rank.
- **Stage 3.11**: Complies strictly with the canonical evaluation contract. **100% of repository files** are indexed and ranked for every query. Zero candidate pre-filtering is permitted.
- **Impact**: When Candidate F is evaluated on the true 100% unconstrained pool, its MRR drops from $0.2078$ to **$0.1338$**.

### 2.5 Metric Definitions: Fractional Recall vs. Binary Hit Rate
- **Stage 3.5**: The Stage 3.5 report presented **Binary Hit@20** under the column heading "Recall@20":
  $$\text{Hit@20}_{\text{CandF}} = \frac{195}{345} = \mathbf{0.565217... \approx 0.5652}$$
  $$\text{Hit@20}_{\text{RepoMap}} = \frac{196}{345} = \mathbf{0.568115... \approx 0.5681}$$
  This binary hit metric was compared against Candidate C's fractional recall ($0.5516$), falsely creating the appearance that Candidate F was competitive with RepoMap.
- **Stage 3.11**: Enforces mathematical fractional recall:
  $$\text{Recall@k} = \frac{|\text{TopK} \cap \text{Gold}|}{|\text{Gold}|}$$
  Under true fractional recall, RepoMap achieves **$0.6599$**, while Candidate F achieves only **$0.5078$**.

### 2.6 Ranking Granularity: File vs. Chunk
- **Stage 3.5**: Fused file-level scores into chunk-level sequences (`rank_and_eval` expanded files into constituent chunks and passed them to ARB's `sample_metrics`).
- **Stage 3.11**: Ranks files directly and measures file-level reciprocal rank and recall from clean-room implementations in `independent_metrics.py`.

### 2.7 Context Packing and Budget Units
- **Stage 3.5**: Counted code tokens via `regex_code_tokenizer_v1` under truncation packing, reporting `0.3184` for Candidate F and `0.3788` for RepoMap (`token_bcy@8k`).
- **Stage 3.10 / 3.11**: Reported both `char_cov@8k` (ARB baseline character-level greedy-stop coverage: $0.0488$ for BM25/Cascade, $0.0652$ for RepoMap) and `token_bcy@8k` ($0.2586$ for Cascade/FunctionGraph, $0.3177$ for RepoMap). The two measurements have distinct units and must never be conflated.

### 2.8 RepoMap Reference Provenance
- **Stage 3.5**: RepoMap was never executed live. The script `research/stage3_5/evaluate_graph_retrieval.py` hardcoded a static dictionary at line 278:
  ```python
  repomap_all = {"mrr": 0.2140, "r5": 0.3185, "r10": 0.4786, "r20": 0.6306, "bcy8k": 0.3788, "lat": 180.20}
  ```
- **Stage 3.6 through Stage 3.11**: Live empirical evaluation of version-pinned official RepoMap on commit `9e4d689` established the true performance: MRR **$0.2293$**, Recall@20 **$0.6599$**, Hit@20 **$0.7101$**.

### 2.9 Oracle Information and Inference-Time Leakage
- **Stage 3.5**: Evaluated a 2-file synthetic micro-fixture for `BurntSushi/ripgrep` containing hardcoded path bypasses (`search.rs`, `standard.rs`) in `evaluate_graph_retrieval.py` lines 97–107, artificially claiming 1.0 MRR on that sample.
- **Stage 3.11**: All hardcoded diagnostic shortcuts are excised. The pipeline operates strictly blind to query gold targets and task types at ranking time.

### 2.10 Evaluator Versions and Code Differences
- **Stage 3.5**: ARB v1.1 evaluation wrapper calling internal `sample_metrics`.
- **Stage 3.11**: Hand-checkable, independent clean-room implementation in `independent_metrics.py` verified by mathematical unit tests in `tests/test_stage3_10_2_integrity.py`.

---

## 3. Summary of Resolved Metrics

Under one uniform, unconstrained canonical evaluation contract ($N = 345$ queries):

| System | Stage 3.5 Claim | Canonical True MRR | Canonical True Recall@20 | Canonical True Hit@20 |
| :--- | :---: | :---: | :---: | :---: |
| **`BASE-BM25`** | 0.1705 | **0.1752** | **0.4535** | **0.5275** |
| **`CAND-C`** | 0.2040 | **0.1401** | **0.5105** | **0.5797** |
| **`CAND-F`** | 0.2152 | **0.1338** | **0.5078** | **0.5739** |
| **`CONTROL-CASCADE`** | N/A | **0.1882** | **0.5503** | **0.6319** |
| **`TEST-GRAPH`** | N/A | **0.1897** | **0.5605** | **0.6435** |
| **`FUNCTION-GRAPH`** | N/A | **0.1901** | **0.5605** | **0.6435** |
| **`FUNCTION-GRAPH-NO-FREEZE`** | N/A | **0.2082** | **0.5648** | **0.6493** |
| **`BASE-REPOMAP`** | 0.2140 (hardcoded) | **0.2293** | **0.6599** | **0.7478** |

**Conclusion**: The claim that Candidate F surpassed RepoMap in Stage 3.5 was the result of candidate pre-filtering, mislabeled binary hit rates, and an unmeasured hardcoded RepoMap reference. Under true canonical conditions, Candidate F collapses to $0.1338$ MRR, while official RepoMap achieves $0.2293$ MRR.
