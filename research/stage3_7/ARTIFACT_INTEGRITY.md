# Artifact Integrity, Provenance & Checksum Audit

**Document ID**: `STAGE3-7-INTEG-001`  
**Stage**: Stage 3.7 — Forensic Evaluation Reconciliation and Research Integrity Audit  
**Date**: October 28, 2026  
**Status**: Authoritative Artifact Manifest  
**Working Branch**: `research-program`  

---

## 1. Executive Summary

This document establishes the authoritative integrity manifest for all research code, evaluation data, and statistical reports across Stages 3.5, 3.6, and 3.7. Every artifact has been verified for existence, non-emptiness, row count, column schema, and SHA-256 cryptographic hash.

The immutable Git tags required by the RepoNeedle research governance charter have been independently verified:
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

### 3.1 Stage 3.5 Artifacts (`research/stage3_5/`)

| Artifact Path | Lines | Bytes | SHA-256 Cryptographic Checksum | Purpose / Description |
| :--- | :---: | :---: | :--- | :--- |
| `research/stage3_5/GRAPH_RETRIEVAL_RESULTS.csv` | 20 | 2,732 | `fc4b0002bafb6b557f22771d78768b8ba94ced0b1f09f9a4658a7d568f55873f` | Historical Stage 3.5 graph evaluation table |
| `research/stage3_5/evaluate_graph_retrieval.py` | 322 | 14,900 | `c81733262347d8680611dc41c5ccb97877373b6c81638adb5059facdf3f59a25` | Stage 3.5 polyglot graph evaluation script |
| `research/stage3_5/CONTEXT_PACKING_RESULTS.csv` | 16 | 1,627 | `edc1f8ac625e2f87f66a94c13f33c68b0090fbfc18cfea69b39431278ab7e708` | Stage 3.5 isolated context packing table |
| `research/stage3_5/evaluate_context_packing.py` | 215 | 10,530 | `7ec53d06ef82cb7c20f00d944ec486e335d6bdcc4890e0e2b88cb9e6bfc783c8` | Context packing evaluation script |
| `research/stage3_5/RUNTIME_AND_MEMORY.csv` | 7 | 841 | `14f30fad81f05d35677b07cb980573ebb9fa7f93dac9156d55a1ff1d89b1bc90` | Isolated memory and latency measurements |
| `research/stage3_5/audit_memory_reduction.py` | 188 | 7,529 | `9042d02a00634b72a3d0285bd4cf0cae157608bac594fbd7a9d23029a44b66bc` | Memory reduction auditing harness |
| `research/stage3_5/BASELINE_REPRODUCTION.md` | 65 | 5,079 | `f8ca35e2aad7faaee3dcd97ee05282c063a4c3e255b8c97ed54e7850950fb2e9` | Stage 3.5 baseline reproduction report |
| `research/stage3_5/FAILURE_ANALYSIS.md` | 166 | 15,081 | `cb9beb08a961d4a3e6d015e4d920af04950af187f4beaa1fe96972972c46c418` | Polyglot failure case analysis |
| `research/stage3_5/STAGE3_5_DECISION_REPORT.md` | 140 | 11,021 | `47778dd7032d0e3fb836da9addb924f9bdfeb2b00b347d888164ba1740d60ca7` | Stage 3.5 provisional decision report |
| `research/stage3_5/EXPERIMENT_REGISTRY.jsonl` | 9 | 3,388 | `ad5cb61790e9b6e1f4b0eb474c70426ba26156ff1e63406b634ab7c46d1efea5` | Stage 3.5 experiment registry |
| `research/stage3_5/reproduce_baseline.py` | 233 | 9,100 | `352828aa6135505ff1c8973a6139d3b12e413243c2c3d9a2467a7bd7a527a9eb` | Baseline replication script |
| `research/stage3_5/test_polyglot_graph.py` | 52 | 2,062 | `111944c302f41d1b1b063781bbb1eb808d98ec48c334dc3eb319f093f15d7242` | Regex unit verification test |
| `research/stage3_5/REPRODUCE.md` | 107 | 4,485 | `cfd3718badcd8445434723b9890d77487bb0b8d3f1807824bf40f1f1532ee59a` | Stage 3.5 reproduction guide |

### 3.2 Stage 3.6 Artifacts (`research/stage3_6/`)

| Artifact Path | Lines | Bytes | SHA-256 Cryptographic Checksum | Purpose / Description |
| :--- | :---: | :---: | :--- | :--- |
| `research/stage3_6/PER_QUERY_RESULTS.csv` | 1,381 | 555,837 | `1311ee12001be7001f645532304e8b1bedd5663f82ab85d57a57c39d792a5007` | Authoritative 4-system per-query predictions (345 queries $\times$ 4 systems + 1 header) |
| `research/stage3_6/PAIRED_STATISTICS.md` | 141 | 7,513 | `f62bcb8dc3c1bc6d68f922b51c0f8b7459377e01e8dfbc6ea77678c59c57abdb` | Clustered bootstrap & Wilcoxon analysis |
| `research/stage3_6/CONTEXT_PACKING_PER_QUERY.csv` | 1,156 | 147,017 | `3527ac6325fb8bc503138292f680b22d1fe70533be02d2837ab992898948ae48` | Per-sample token context yield data |
| `research/stage3_6/CONTEXT_PACKING_RESULTS.csv` | 16 | 1,582 | `3e31d0dccfcad9e9f86db7f4ed2db576b0ea269097fbdb847cc3b485795e0dff` | Token context packing summary |
| `research/stage3_6/RUNTIME_MEMORY_RESULTS.csv` | 13 | 1,610 | `af763eca98bc94e1fbf31675a0c86c18da07a7ab99341917aca54838f5f73379` | Multi-corpus latency & memory profile |
| `research/stage3_6/evaluate_systems.py` | 356 | 15,476 | `0bff8defaf1ec4f914454b9e4db5208ee113c1459b9a757bc4ab421ce3b899d8` | Unified four-system evaluation harness |
| `research/stage3_6/compute_paired_statistics.py` | 346 | 14,573 | `27a125220f9dfcb81411b7668865f0220213e6ca66628c44e29edffafc72ad7b` | Statistical computation engine |
| `research/stage3_6/audit_context_packing.py` | 223 | 11,143 | `5bbf9d995f9d5235bed5dc0ed45864b482b8fb9c33a5440fa8501c7cc715a721` | Context packing audit harness |
| `research/stage3_6/audit_runtime_and_memory.py` | 207 | 7,855 | `dc4ab069556141eb114c2ecff1276353a6d91d72a02fd38bcbb56f3423474508` | Runtime and memory audit harness |
| `research/stage3_6/GRAPH_AUDIT.md` | 127 | 8,384 | `b5a17a7474264beb46a8e81bc12e490e688c5a656d59b70284fd325bd65f324a` | Hardcoded graph edge audit report |
| `research/stage3_6/FAILURE_ANALYSIS.md` | 108 | 8,841 | `1e3d086438fe01b4ecdd94f32cd82ce81c2bfe9d0cd58af425427a844b4d7661` | Regression breakdown by repository |
| `research/stage3_6/DECISION_REPORT.md` | 82 | 6,595 | `45a7c94c88a18887371b8c7838f821bcd86f3b00e6a97e7f1add32dc30039ffd` | Stage 3.6 decision report |
| `research/stage3_6/REPRODUCIBILITY_REPORT.md` | 85 | 6,517 | `c4f963ea1d1fb308807946f3e9bcd3d17b3b57833b44ff31262620d6bf9fd600` | Stage 3.6 reproducibility audit |
| `research/stage3_6/EXPERIMENT_REGISTRY.jsonl` | 7 | 2,064 | `189128193b2857d4e578f28d4e13601a52805272dc117c824fe60d10dabedd02` | Stage 3.6 experiment registry |
| `research/stage3_6/REPRODUCE.md` | 126 | 5,465 | `33644f6fdf5da1d7233e74fd82ff7b814cb5dac903865d1ca26e93a56373d8d6` | Stage 3.6 reproduction instructions |

### 3.3 Stage 3.7 Artifacts (`research/stage3_7/`)

| Artifact Path | Lines | Bytes | SHA-256 Cryptographic Checksum | Purpose / Description |
| :--- | :---: | :---: | :--- | :--- |
| `research/stage3_7/EVALUATION_RECONCILIATION.md` | 101 | 11,246 | `535c2f6dc32d1eb8c8bc03a47301afa6d0fc518e438535b5d909261a01885342` | Master forensic evaluation reconciliation report |
| `research/stage3_7/METRIC_CONTRACT.md` | 161 | 9,575 | `5e3a26263e2c94267057113c2d09afa05a73a4ac0684b1e1d92b26354d58f0e4` | Binding mathematical metric contract |
| `research/stage3_7/STATISTICAL_AUDIT.md` | 97 | 7,823 | `b4b8b040eb9f1fa83b20f8bf6c4e0382031fdec7bd0d650611e09de6106d4e92` | Clustered bootstrap vs Wilcoxon variance audit |
| `research/stage3_7/LATENCY_MEMORY_AUDIT.md` | 92 | 6,420 | `800c36a523819d169b0ecfc36be1b84bb42ac14b9e2467e0fdb37e016e4915d7` | Scale-dependent latency & process RSS audit |
| `research/stage3_7/DECISION_REPORT.md` | 65 | 5,720 | `524161caf82ee804107a368e1f93d86710b6cee750f946cf13861df12056bc4a` | Official Stage 3.7 verdict & directives |
| `research/stage3_7/REPRODUCE.md` | 107 | 3,616 | `d4e793cdce50ed33ea86fdc7208ddf438ad63978a4a33d1de3b63b752c547061` | Step-by-step reproduction instructions |
| `research/stage3_7/EXPERIMENT_REGISTRY.jsonl` | 6 | 1,917 | `1bc5d7acebf9335d673c6ea0a7f78224a89c81e016edd7adbb5cd5b5ecfe7f95` | Stage 3.7 forensic experiment entries |
| `tests/test_stage3_7_metrics.py` | 189 | 7,733 | `86b6e871d247f0458aa493c2141762728d078dd318a1c9a9b30f2da4a38535cf` | Automated regression unit tests (9 tests) |

---

## 4. Primary Dataset Provenance & Schema Verification

The authoritative dataset `research/stage3_6/PER_QUERY_RESULTS.csv` adheres to the following pinned specification:
- **Total Line Count**: Exactly 1,381 lines (1 CSV header + 1,380 query prediction rows).
- **Query Count**: Exactly 345 unique query IDs across 4 systems ($345 \times 4 = 1,380$ rows).
- **Evaluated Systems**:
  1. `BASE-BM25` (345 rows)
  2. `CAND-C` (345 rows)
  3. `CAND-F` (345 rows)
  4. `BASE-REPOMAP` (345 rows)
- **Column Schema (23 fields)**:
  `query_id, repo, task_type, language, system_id, mrr, recall_at_1, recall_at_5, recall_at_10, recall_at_20, precision_at_5, precision_at_10, precision_at_20, bcy_at_4k, bcy_at_8k, bcy_at_16k, first_relevant_rank, retrieved_token_count, selected_file_count, latency_ms, abstained, gold_files, top_ranked_paths`
- **Data Integrity**: Zero missing values, zero unhandled exceptions, zero NaN entries.
