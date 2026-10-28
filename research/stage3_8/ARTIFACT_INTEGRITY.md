# Stage 3.8: Artifact Integrity, Checksums & Provenance Manifest

**Document ID**: `STAGE3-8-INTEG-001`  
**Stage**: Stage 3.8 — Reproducibility Lock, Metric Reconciliation, and Evidence Audit  
**Date**: October 28, 2026  
**Status**: Authoritative Artifact Manifest  
**Working Branch**: `research-program`  

---

## 1. Executive Summary

This manifest provides cryptographic verification and provenance tracking for all research code, benchmark evaluations, and reconciliation artifacts across Stages 3.5, 3.6, 3.7, and 3.8.

The immutable Git tags required by the RepoNeedle research charter have been verified:
- **`v0.1.0-baseline`**: `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` (Clean, Untouched)
- **`stage3-candidate-freeze`**: `cd7f3b01e28695f9a9357e0815069e0eae85baca` (Clean, Untouched)

Neither tag has been moved, rewritten, or modified.

---

## 2. Frozen Tag Verification

```powershell
git rev-parse "v0.1.0-baseline^{commit}" "stage3-candidate-freeze^{commit}"
```
- Output:
  ```
  8e0042553a14b6e3c6cf5b35823c4da84181a8e9
  cd7f3b01e28695f9a9357e0815069e0eae85baca
  ```
- **Integrity Status**: **VERIFIED IMMUTABLE**.

---

## 3. Comprehensive Artifact Manifest & Checksum Table

### 3.1 Stage 3.8 Canonical Artifacts (`research/stage3_8/`)

| Artifact Path | Lines | Bytes | SHA-256 Cryptographic Checksum | Purpose / Description |
| :--- | :---: | :---: | :--- | :--- |
| `research/stage3_8/CANONICAL_PER_QUERY_RESULTS.csv` | 1,381 | 681,499 | `430574460e5339e692c6fbefcc07604b2ee9840d551aeda1e1321981483ad929` | Canonical 4-system ARB v2 predictions (345 queries $\times$ 4 systems + 1 header) |
| `research/stage3_8/REPRODUCIBILITY_AUDIT.md` | 149 | 11,766 | `68969d31a44af9c9f6504a465f2e3058f779b01c1cf7b5ebbf4f3cfc9e0eb98e` | Forensic investigation of the 7 disputed historical claims |
| `research/stage3_8/RESULT_DISCREPANCY_MATRIX.csv` | 20 | 5,052 | `0c524a9112e8a0b0755ccdd3092aa5fb4ab8234c99b409d7883e434dae818f49` | Structured tabular discrepancy matrix mapping all claims |
| `research/stage3_8/CANONICAL_METRIC_CONTRACT.md` | 112 | 6,271 | `e74c8daf8879aa0aa0467fbe0c7a9da66f02183820c7e443f889b22740b0dee0` | Authoritative mathematical contract for all future work |
| `research/stage3_8/STATISTICAL_RECONCILIATION.md` | 92 | 8,406 | `155feb0f5cb0ca7dee4ccd0a1b1f1e408d9d6b81191adcc51ccf8ddced5106c4` | Authoritative clustered bootstrap ($B=10,000$) & Wilcoxon audit |
| `research/stage3_8/RUNTIME_MEMORY_RECONCILIATION.md`| 81 | 5,840 | `12734334e3dea72b91817ce479f4364848a6a1119732d5186ce6e4db02e27c49` | Scale-dependent latency distribution & OS process RSS audit |
| `research/stage3_8/DECISION_REPORT.md` | 74 | 5,469 | `d0e90924acb1b4f67827011976d5035060978358dddddf1decdacc3d9b43321e` | Authoritative Stage 3.8 verdict & governance report |
| `research/stage3_8/REPRODUCE.md` | 122 | 3,740 | `2b87ed7e3c6b056b78d4c69b4d00204c6d8beb2c421065e81fb77ba10e89c67f` | Step-by-step reproduction guide and verification commands |
| `research/stage3_8/EXPERIMENT_REGISTRY.jsonl` | 6 | 1,859 | `7cdd10f4a4d829c236649f49b4e3c6f3d48bee98815aaebf7f81075f4910c9e8` | Structured ledger of Stage 3.8 experiments (EXP-381 - EXP-386) |
| `research/stage3_8/build_canonical_results.py` | 139 | 5,511 | `13d1c137f33eca6a0065258a23ac1a4298be7bb313cc232c6d8f582d753d92d1` | Generator script for canonical per-query predictions |
| `tests/test_stage3_8_reproducibility.py` | 152 | 6,694 | `d6fe413f92e61c8f2beca298cdf54ba30c421e2305bcf9027f71cc1a07d19a12` | Automated unit regression tests (8 tests passing) |

### 3.2 Stage 3.7 Historical Audit Artifacts (`research/stage3_7/`)

| Artifact Path | Lines | Bytes | SHA-256 Cryptographic Checksum | Purpose / Description |
| :--- | :---: | :---: | :--- | :--- |
| `research/stage3_7/EVALUATION_RECONCILIATION.md` | 101 | 11,246 | `535c2f6dc32d1eb8c8bc03a47301afa6d0fc518e438535b5d909261a01885342` | Stage 3.7 initial reconciliation document |
| `research/stage3_7/METRIC_CONTRACT.md` | 161 | 9,575 | `5e3a26263e2c94267057113c2d09afa05a73a4ac0684b1e1d92b26354d58f0e4` | Stage 3.7 metric contract draft |
| `research/stage3_7/STATISTICAL_AUDIT.md` | 97 | 7,823 | `b4b8b040eb9f1fa83b20f8bf6c4e0382031fdec7bd0d650611e09de6106d4e92` | Stage 3.7 statistical audit draft |
| `research/stage3_7/LATENCY_MEMORY_AUDIT.md` | 92 | 6,420 | `800c36a523819d169b0ecfc36be1b84bb42ac14b9e2467e0fdb37e016e4915d7` | Stage 3.7 latency and memory draft |
| `research/stage3_7/DECISION_REPORT.md` | 65 | 5,720 | `524161caf82ee804107a368e1f93d86710b6cee750f946cf13861df12056bc4a` | Stage 3.7 decision report draft |
| `research/stage3_7/REPRODUCE.md` | 107 | 3,616 | `d4e793cdce50ed33ea86fdc7208ddf438ad63978a4a33d1de3b63b752c547061` | Stage 3.7 reproduction instructions |
| `research/stage3_7/EXPERIMENT_REGISTRY.jsonl` | 6 | 1,917 | `1bc5d7acebf9335d673c6ea0a7f78224a89c81e016edd7adbb5cd5b5ecfe7f95` | Stage 3.7 experiment registry |
| `tests/test_stage3_7_metrics.py` | 189 | 7,733 | `86b6e871d247f0458aa493c2141762728d078dd318a1c9a9b30f2da4a38535cf` | Stage 3.7 regression unit tests |

### 3.3 Stage 3.6 Authoritative Source Artifacts (`research/stage3_6/`)

| Artifact Path | Lines | Bytes | SHA-256 Cryptographic Checksum | Purpose / Description |
| :--- | :---: | :---: | :--- | :--- |
| `research/stage3_6/PER_QUERY_RESULTS.csv` | 1,381 | 555,837 | `1311ee12001be7001f645532304e8b1bedd5663f82ab85d57a57c39d792a5007` | Base per-query raw predictions |
| `research/stage3_6/PAIRED_STATISTICS.md` | 141 | 7,513 | `f62bcb8dc3c1bc6d68f922b51c0f8b7459377e01e8dfbc6ea77678c59c57abdb` | Clustered bootstrap paired calculations |
| `research/stage3_6/CONTEXT_PACKING_PER_QUERY.csv` | 1,156 | 147,017 | `3527ac6325fb8bc503138292f680b22d1fe70533be02d2837ab992898948ae48` | Per-query context packing records |
| `research/stage3_6/CONTEXT_PACKING_RESULTS.csv` | 16 | 1,582 | `3e31d0dccfcad9e9f86db7f4ed2db576b0ea269097fbdb847cc3b485795e0dff` | Context packing summary table |
| `research/stage3_6/RUNTIME_MEMORY_RESULTS.csv` | 13 | 1,610 | `af763eca98bc94e1fbf31675a0c86c18da07a7ab99341917aca54838f5f73379` | Multi-tier latency and memory data |

---

## 4. Canonical Dataset Specification & Validation

The authoritative dataset `research/stage3_8/CANONICAL_PER_QUERY_RESULTS.csv` adheres to the following specification:
- **Total Line Count**: Exactly 1,381 lines (1 header + 1,380 query rows).
- **Query Alignment**: Exactly 345 unique query IDs evaluated across 4 systems in identical sequence.
- **Completeness**: 0 missing values, 0 failed queries, 0 excluded samples.
- **Fields (27 columns)**:
  `query_id, repo, base_commit, task_type, language, system_id, candidate_config_id, mrr, recall_at_1, recall_at_5, recall_at_10, recall_at_20, precision_at_5, precision_at_10, precision_at_20, char_cov_at_4k, char_cov_at_8k, char_cov_at_16k, token_bcy_at_8k, first_relevant_rank, retrieved_token_count, selected_file_count, latency_ms, abstained, execution_status, gold_files, top_ranked_paths`
