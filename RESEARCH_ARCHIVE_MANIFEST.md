# RepoNeedle — Research Archive Manifest (Mission 0.80+ Phases R1–R6)

**Document Version**: 1.0.0  
**Author**: Senior Release Engineer & Research Auditor  
**Date**: November 2026  
**Archive Branch**: `origin/research/v1.1-change-impact-archive` (Commit: `1d179ae`)  
**Secondary Branch**: `origin/v1.1-change-impact` (Commit: `d72ffcf`)  
**Total Preserved Research Files**: **199 files**  
**Total Lines of Research**: **38,609 lines**  
**Total Archive Size**: **4,134.5 KB (~4.1 MB)**

---

## 1. Executive Summary & Archival Purpose

To maintain production reviewability, the 199 research files from Mission 0.80+ (Phases R1 through R6 and the V1.1 Audit) have been separated from the core production release Pull Request ([PR #2](https://github.com/krishika08/RepoNeedle/pull/2)) into a dedicated, permanent research archive.

This manifest provides the exhaustive inventory, provenance, and reproduction roadmap for all preserved research assets. **Zero research files, evaluation records, or benchmark datasets have been deleted or modified.**

---

## 2. Archival Summary by Phase

| Research Phase | Scope & Objective | Files | LoC | Key Artifacts |
| :--- | :--- | :---: | :---: | :--- |
| **Phase R1 Core** | Ranking Forensics & MRR Loss Taxonomy | 7 | 1,440 | `RANKING_FORENSIC_REPORT.md`, `QUERY_FAILURE_TAXONOMY.md`, `MRR_LOSS_ANALYSIS.md` |
| **Phase R1 Scripts** | Baseline Reproduction & Headroom Simulation | 16 | 1,515 | `compute_headroom.py`, `cross_correlate.py`, `reproduce_baseline.py` |
| **Phase R2** | Seed File Suppression (SFS) & Test Intent Priors (TIP) | 25 | 3,366 | `PER_QUERY_COMPARISON.jsonl` (345 queries), `ranker_r2.py`, `seed_suppression.py` |
| **Phase R3** | AST Symbol Intelligence & BM25 Variants (BM25L) | 34 | 4,213 | `PER_QUERY_COMPARISON.jsonl` (345 queries), `ast_symbol.py`, `bm25_variants.py` |
| **Phase R4** | Dense Semantic SVD & Multi-Hop Structural BFS | 28 | 4,275 | `PER_QUERY_COMPARISON.jsonl` (345 queries), `dense_semantic.py`, `multihop_graph.py` |
| **Phase R5** | Code-Unit Indexing & Typed Change-Impact Graphs | 35 | 5,528 | `PER_QUERY_COMPARISON.jsonl` (345 queries), `code_unit.py`, `change_impact.py` |
| **Phase R6** | Independent 18-Repo Benchmark & Generalization | 32 | 7,668 | `PER_QUERY_RESULTS.jsonl` (1,440 evals), `independent_benchmark.json.gz` |
| **V1.1 Audit** | Final Integrity, Forensic Accounting & Parity | 17 | 9,756 | `METRIC_RECONCILIATION.md`, `run_reproducible_benchmark.py`, `production_champion_config.json` |
| **Research Tests** | Regression Test Suites for Research Rankers | 5 | 848 | `test_ranking_r2.py`, `r3.py`, `r4.py`, `r5.py`, `r6.py` |
| **TOTAL** | **Full Mission 0.80+ Archive** | **199** | **38,609** | **100% Preserved with Verified Provenance** |

---

## 3. Detailed Phase Inventories

### 3.1 Phase R1: Ranking Forensics & Taxonomy (23 Files)
Located at: `research/v1_accuracy/ranking_0_80/`
- **Reports (7 files)**:
  - `BASELINE_REPRODUCTION.json` (9,595 lines: Full baseline per-query logs)
  - `EXPERIMENT_PLAN.md` (169 lines: Mission 0.80+ roadmap)
  - `FEATURE_OPPORTUNITIES.md` (196 lines: Feature engineering space)
  - `MRR_LOSS_ANALYSIS.md` (174 lines: Mathematical breakdown of MRR headroom)
  - `QUERY_FAILURE_TAXONOMY.md` (465 lines: 6-part failure classification)
  - `R1_DECISION_REPORT.md` (122 lines: R1 baseline freeze)
  - `RANKING_FORENSIC_REPORT.md` (198 lines: In-depth query failure forensics)
- **Common Simulation Scripts (16 files)**:
  - `scripts/analyze_displacers.py`, `classify_taxonomy.py`, `combined_simulation.py`, `compute_headroom.py`, `cross_correlate.py`, `deep_forensics.py`, `design_repo_split.py`, `generate_baseline_json.py`, `generate_taxonomy_report.py`, `inspect_datasets.py`, `inspect_query_distractors.py`, `investigate_c2t.py`, `reproduce_baseline.py`, `seed_displacement.py`, `simulate_seed_exclusion.py`, `test_boosting_simulation.py`.

### 3.2 Phase R2: SFS & TIP Ranker (25 Files)
Located at: `research/v1_accuracy/ranking_0_80/r2/`
- **Benchmark Datasets & Summaries**:
  - `PER_QUERY_COMPARISON.jsonl` (345 query lines: R2 Treatments A–H)
  - `held_out_evaluation.json` (62 lines: Held-out validation metrics)
  - `statistical_summary.json` (514 lines: Bootstrap & permutation test distributions)
- **Reports (8 files)**:
  - `CLASSIFIER_EVALUATION.md`, `EXPERIMENT_RESULTS.md`, `FEATURE_SCHEMA.md`, `R2_EXPERIMENT_DESIGN.md`, `R2_FINAL_DECISION_REPORT.md`, `SFS_IMPLEMENTATION_REPORT.md`, `SMS_IMPLEMENTATION_REPORT.md`, `STATISTICAL_VALIDATION.md`, `TIP_IMPLEMENTATION_REPORT.md`.
- **Implementation & Evaluation Scripts (13 files)**:
  - `src/eval_classifier_val.py`, `evaluate_r2.py`, `export_all_jsonl.py`, `inspect_all_training.py`, `inspect_train_queries.py`, `ranker_r2.py`, `run_ablations.py`, `run_held_out.py`, `seed_suppression.py`, `split.py`, `statistical_validation.py`, `stem_symmetry.py`, `test_intent.py`.

### 3.3 Phase R3: AST Symbol Intelligence & BM25 Variants (34 Files)
Located at: `research/v1_accuracy/ranking_0_80/r3/`
- **Benchmark Datasets & Summaries**:
  - `PER_QUERY_COMPARISON.jsonl` (345 query lines: Treatments A–I)
  - `master_metrics.json` (416 lines: Multi-treatment breakdown)
  - `statistical_summary.json` (67 lines: Clustered p-values)
- **Reports (11 files)**:
  - `AST_SYMBOL_DESIGN.md`, `AST_SYMBOL_IMPLEMENTATION_REPORT.md`, `BM25_EXPERIMENT_REPORT.md`, `BM25_VARIANT_ANALYSIS.md`, `EXPERIMENT_RESULTS.md`, `FEATURE_SCHEMA.md`, `NEW_HELDOUT_EVALUATION.md`, `R3_BASELINE_AUDIT.md`, `R3_DATA_GOVERNANCE.md`, `R3_FINAL_DECISION_REPORT.md`, `STATISTICAL_VALIDATION.md`.
- **Implementation & Analysis Scripts (20 files)**:
  - `src/ast_symbol.py`, `audit_r2_baseline.py`, `bm25_variants.py`, `check_exact_symbol_dist.py`, `check_gold_types.py`, `check_score_scales.py`, `evaluate_r3.py`, `experiment_prototype.py`, `extract_breakdowns.py`, `find_new_repos.py`, `inspect_chunks.py`, `inspect_m1_scores.py`, `inspect_tasks.py`, `print_master_table.py`, `ranker_r3.py`, `statistical_validation.py`, `test_ast_symbol_extract.py`, `test_chunk_loading.py`, `test_conditioned_ast.py`, `test_r3_combinations.py`.

### 3.4 Phase R4: Dense Semantic & Multi-Hop Structural Retrieval (28 Files)
Located at: `research/v1_accuracy/ranking_0_80/r4/`
- **Benchmark Datasets & Summaries**:
  - `PER_QUERY_COMPARISON.jsonl` (345 query lines: Treatments A–G)
  - `master_metrics.json` (310 lines)
  - `resource_benchmarks.json` (52 lines: RAM & latency profiles)
  - `statistical_summary.json` (68 lines)
- **Reports (11 files)**:
  - `DENSE_RETRIEVAL_DESIGN.md`, `DENSE_RETRIEVAL_RESULTS.md`, `HYBRID_EXPERIMENT_RESULTS.md`, `HYBRID_FUSION_DESIGN.md`, `MULTIHOP_GRAPH_DESIGN.md`, `MULTIHOP_GRAPH_RESULTS.md`, `NEW_HELDOUT_EVALUATION.md`, `R4_BASELINE_AUDIT.md`, `R4_DATA_GOVERNANCE.md`, `R4_FINAL_DECISION_REPORT.md`, `STATISTICAL_VALIDATION.md`.
- **Implementation Scripts (13 files)**:
  - `src/audit_heldout_leakage.py`, `dense_semantic.py`, `evaluate_r4.py`, `generate_master_metrics.py`, `hybrid_fusion.py`, `multihop_graph.py`, `ranker_r4.py`, `resource_profiler.py`, `run_full_validation.py`, `statistical_validation.py`, `test_dense_semantic.py`, `test_hybrid_fusion.py`, `test_multihop_graph.py`.

### 3.5 Phase R5: Code-Unit Indexing & Change-Impact Engine (35 Files)
Located at: `research/v1_accuracy/ranking_0_80/r5/`
- **Benchmark Datasets & Summaries**:
  - `PER_QUERY_COMPARISON.jsonl` (345 query lines: Treatments A–F)
  - `audit_statistics.json` (382 lines)
  - `master_metrics.json` (466 lines)
  - `resource_benchmarks.json` (57 lines)
  - `statistical_summary.json` (427 lines)
- **Reports (17 files)**:
  - `CODE_UNIT_INDEXING_DESIGN.md`, `CODE_UNIT_INDEXING_REPORT.md`, `EXPERIMENT_RESULTS.md`, `FAILURE_ANALYSIS_REPORT.md`, `FEATURE_SCHEMA.md`, `FINAL_VERIFICATION_REPORT.md`, `MULTI_TARGET_SELECTOR_REPORT.md`, `NEW_HELDOUT_EVALUATION.md`, `PRODUCTION_INTEGRATION_READINESS.md`, `QUERY_ALIGNMENT_REPORT.md`, `R5_BASELINE_AUDIT.md`, `R5_FINAL_DECISION_REPORT.md`, `R5_PROMOTION_AUDIT.md`, `R5_PROMOTION_DECISION.md`, `REPOSITORY_OVERLAP_AUDIT.md`, `RESOURCE_BENCHMARKS.md`, `STATISTICAL_REVALIDATION.md`, `STATISTICAL_VALIDATION.md`.
- **Implementation Scripts (13 files)**:
  - `src/audit_provenance_and_statistics.py`, `change_impact.py`, `code_unit.py`, `evaluate_r5.py`, `inspect_sample.py`, `multi_target.py`, `pilot_test.py`, `query_alignment.py`, `ranker_r5.py`, `resource_profiler_r5.py`, `statistical_validation_r5.py`, `test_code_unit.py`.

### 3.6 Phase R6: Independent 18-Repository Cohort Benchmark (32 Files)
Located at: `research/v1_accuracy/ranking_0_80/r6/`
- **Benchmark Datasets**:
  - `PER_QUERY_RESULTS.jsonl` (1,440 query evaluation lines: 18 repos $\times$ 10 queries $\times$ 8 treatments)
  - `independent_benchmark.json.gz` (104.5 KB compressed JSON: Complete 18-repository AST graphs and query manifests)
  - `master_metrics.json` (272 lines: Authoritative partition metrics)
  - `graph_evidence_audit.json` (28 lines)
  - `performance_benchmarks.json` (20 lines)
  - `statistical_summary.json` (104 lines: Clustered paired t-test distributions)
- **Reports (18 files)**:
  - `BASELINE_COMPARISON.md`, `BENCHMARK_SCHEMA.md`, `DATA_PROVENANCE.md`, `EXPERIMENT_RESULTS.md`, `GOLD_ANNOTATION_PROTOCOL.md`, `GRAPH_EVIDENCE_AUDIT.md`, `INDEPENDENT_HELDOUT_REPORT.md`, `R6_BENCHMARK_FORENSIC_AUDIT.md`, `R6_FINAL_DECISION_REPORT.md`, `R6_FINAL_PROMOTION_DECISION.md`, `R6_GRAPH_METRIC_RECONCILIATION.md`, `R6_INTEGRATION_DESIGN.md`, `R6_INTEGRATION_TEST_REPORT.md`, `R6_PERFORMANCE_REPORT.md`, `R6_RESEARCH_DESIGN.md`, `R6_STATISTICAL_REVALIDATION.md`, `R6_TREATMENT_RECONCILIATION.md`, `REPOSITORY_SELECTION_REPORT.md`, `STATISTICAL_VALIDATION.md`.
- **Implementation Scripts (7 files)**:
  - `src/audit_graph_evidence.py`, `benchmark_dataset.py`, `benchmark_performance.py`, `evaluate_r6.py`, `graph_evidence.py`, `ranker_r6.py`, `task_definitions.py`.

### 3.7 V1.1 Release Audit & Reconciliation (17 Files)
Located at: `research/v1_accuracy/ranking_0_80/v1_1_audit/`
- **Audit Reports & Manifests (9 files)**:
  - `CHAMPION_CONFIGURATION_AUDIT.md`, `FINAL_V1_1_INTEGRITY_DECISION.md`, `INCREMENTAL_INDEXING_AUDIT.md`, `METRIC_RECONCILIATION.md`, `PACKAGE_INSTALLATION_REPORT.md`, `PRODUCTION_API_CLI_AUDIT.md`, `PULL_REQUEST_DESCRIPTION.md`, `REGRESSION_TEST_REPORT.md`, `REPRODUCIBILITY_GUIDE.md`.
- **Champion Configs & Checksums**:
  - `production_champion_config.json` (SHA-256: `74b1075938e75504a062024dcd0008840f7e2a349d9cb60c00146ee0a6681c9d`)
  - `incremental_benchmarks.json`, `reproducible_benchmark_run.json`.
- **Verification & Parity Scripts (5 files)**:
  - `benchmark_incremental.py`, `run_live_audit_test.py`, `run_reproducible_benchmark.py`, `test_incremental_concept.py`, `test_wheel_install.py`.

### 3.8 Research Regression Tests (5 Files)
Located at: `tests/`
- `tests/test_ranking_r2.py` (119 lines, 6 tests)
- `tests/test_ranking_r3.py` (131 lines, 8 tests)
- `tests/test_ranking_r4.py` (228 lines, 8 tests)
- `tests/test_ranking_r5.py` (189 lines, 8 tests)
- `tests/test_ranking_r6.py` (181 lines, 8 tests)

---

## 4. Reproducibility Roadmap

To reproduce any historical research result:
1. Check out the research archive branch:
   ```bash
   git checkout research/v1.1-change-impact-archive
   ```
2. Run the certified, single-command benchmark runner:
   ```bash
   python research/v1_accuracy/ranking_0_80/v1_1_audit/run_reproducible_benchmark.py
   ```
   *Execution time: ~0.50 seconds. Output certified to `reproducible_benchmark_run.json`.*
3. Run the research test regression suite:
   ```bash
   pytest tests/test_ranking_r*.py -v
   ```
