# RepoNeedle Stage 3.15 — Test and Reproduction Audit Log

**Document ID**: `STAGE3-15-TESTLOG-001`  
**Date**: October 2026  
**Auditor**: Autonomous Verification Harness  
**Workspace**: `F:\RepoNeedle`  
**Current Branch**: `research-program`  
**Commit SHA**: `12142e8`  

---

## 1. Execution Environment & Dependencies

| Component | Verified Specification |
|---|---|
| **Operating System** | Windows 11 Enterprise (x64, Build 26100) |
| **Python Version** | Python 3.12.10 (AMD64) |
| **Pytest Version** | pytest-9.1.1 (pluggy-1.6.0) |
| **NumPy Version** | 2.2.3 |
| **SciPy Version** | 1.15.2 |
| **Networkx Version** | 3.4.2 |
| **Tree-sitter** | tree-sitter-0.24.0 |
| **Git Working Tree** | Clean (`nothing to commit, working tree clean`) |
| **Baseline Tag `v0.1.0-baseline`** | `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` (Verified Unchanged) |
| **Freeze Tag `stage3-candidate-freeze`** | `cd7f3b01e28695f9a9357e0815069e0eae85baca` (Verified Unchanged) |

---

## 2. Test Suite Execution Records

### Test Run 1: Full Repository Test Suite (Regression & Integrity Suite)
- **Command**: `pytest`
- **Working Directory**: `F:\RepoNeedle`
- **Exit Code**: `0` (Success)
- **Results**: **177 passed in 6.20s**
- **Test Modules Executed**:
  1. `tests/test_ablation_switches.py`: 5 passed
  2. `tests/test_abstention.py`: 2 passed
  3. `tests/test_benchmark.py`: 4 passed
  4. `tests/test_budget.py`: 2 passed
  5. `tests/test_engine.py`: 2 passed
  6. `tests/test_graph.py`: 8 passed
  7. `tests/test_lexical.py`: 3 passed
  8. `tests/test_robustness_and_quality.py`: 9 passed
  9. `tests/test_router.py`: 4 passed
  10. `tests/test_semantic.py`: 2 passed
  11. `tests/test_stage3_10_1_metric_validation.py`: 6 passed
  12. `tests/test_stage3_10_2_integrity.py`: 5 passed
  13. `tests/test_stage3_10_class_to_test.py`: 10 passed
  14. `tests/test_stage3_10_verification.py`: 4 passed
  15. `tests/test_stage3_11_function_graph.py`: 6 passed
  16. `tests/test_stage3_11_integrity.py`: 5 passed
  17. `tests/test_stage3_12_factorial.py`: 7 passed
  18. `tests/test_stage3_12_hardening.py`: 5 passed
  19. `tests/test_stage3_12a_reconciliation.py`: 4 passed
  20. `tests/test_stage3_13_reconciliation.py`: 5 passed
  21. `tests/test_stage3_14_language_attenuation.py`: 6 passed
  22. `tests/test_stage3_14_safeguards.py`: 7 passed
  23. `tests/test_stage3_15_safeguards.py`: 7 passed
  24. `tests/test_stage3_6_forensic_reconciliation.py`: 6 passed
  25. `tests/test_stage3_7_fail_closed_audit.py`: 7 passed
  26. `tests/test_stage3_7_metrics.py`: 9 passed
  27. `tests/test_stage3_8_reproducibility.py`: 8 passed
  28. `tests/test_stage3_9_2_budget_audit.py`: 7 passed
  29. `tests/test_stage3_9_cascade.py`: 9 passed
  30. `tests/test_stage3_9_recovery.py`: 4 passed
  31. `tests/test_stage3_candidates.py`: 5 passed
  32. `tests/test_tokenizer.py`: 4 passed

### Test Run 2: ContextBench Fail-Closed Gate & Adapter Integrity
- **Command**: `pytest tests/test_stage3_15_safeguards.py -v`
- **Working Directory**: `F:\RepoNeedle`
- **Exit Code**: `0` (Success)
- **Results**: `7 passed in 0.54s`
- **Assertions Verified**:
  - `test_frozen_tags_immutability`: Tags remain identical to documented immutable SHAs.
  - `test_missing_dataset_fails_closed`: Exit code 2 returned when data directory is missing.
  - `test_checksum_mismatch_fails_closed`: Exit code 3 returned when dataset hash fails SHA-256 match.
  - `test_incorrect_schema_fails_closed`: Exit code 4 returned when query or gold files are invalid.
  - `test_missing_task_predictions_surfaced`: Empty predictions yield 0.0 scores with explicit error status.
  - `test_evaluator_adapter_freezes_configurations`: Immutable parameter factories locked.
  - `test_acquisition_attempts_provenance_record`: Provenance record verifies HTTP 403 sandbox blocker.

---

## 3. Test Characterization: Algorithmic Correctness vs Structure

- **Algorithmic Correctness Tests**:
  - `test_graph.py`, `test_lexical.py`, `test_engine.py`, `test_stage3_11_function_graph.py`, `test_stage3_10_class_to_test.py`: Validate graph edge generation, Okapi BM25 formula calculation, class invocation tracking, and reranking logic.
- **Protocol Safeguard Tests**:
  - `test_stage3_14_safeguards.py`, `test_stage3_15_safeguards.py`: Validate fail-closed boundary enforcement, tag immutability, dataset schema compliance, and errata banner presence.
- **No tests were modified, relaxed, or disabled** to achieve a green test suite.

---

## 4. Script Reproducibility & Resource Cleanup Verification

1. **Deterministic Execution**:
   - Running `python research/stage3_15/generate_stage3_15_reconciliation.py` regenerates all 5 machine-readable deliverables (`BASELINE_DISCREPANCIES.csv`, `CLAIM_VERIFICATION.csv`, `CANONICAL_SCOREBOARD.csv`, `REPRODUCED_PER_QUERY_RESULTS.csv`, `EXPERIMENT_REGISTRY.jsonl`) deterministically in under 3.5 seconds.
2. **Resource Cleanliness**:
   - Zero zombie processes or background tasks remained running.
   - All temporary background processes were terminated and verified clean.
