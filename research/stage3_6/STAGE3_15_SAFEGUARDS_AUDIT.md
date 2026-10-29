# RepoNeedle Stage 3.6: Audit of Stage 3.15 Independent-Evaluation Safeguards

**Document ID**: `STAGE3-6-SAFEGUARDS-001`  
**Date**: October 2026  
**Stage**: Stage 3.6 — Forensic Reproducibility and Candidate F Validation Gate  
**Branch**: `research-program`  
**Base Commit**: `29bb3b9`  

---

## 1. Executive Summary

This audit verifies that the independent evaluation safeguards, fail-closed validation gates, and pre-registered configuration registries established in Stage 3.15 remain completely intact, and that Stage 3.5's Candidate F investigations have not compromised or contaminated the independent benchmark protocol.

---

## 2. Safeguard Verification Checklist

| Safeguard Specification | Implementation / Artifact | Verification Evidence | Audit Verdict |
| :--- | :--- | :--- | :--- |
| **No Synthetic Dataset Substitution** | [`research/stage3_15/DATASET_PROVENANCE.md`](file:///F:/RepoNeedle/research/stage3_15/DATASET_PROVENANCE.md) | The 19-instance micro-suite (`research/stage3/data/contextbench_suite.json`) is explicitly quarantined and prohibited from being substituted as ContextBench. | **VERIFIED & COMPLIANT** |
| **Fail-Closed Dataset Validation** | [`research/stage3_15/validate_contextbench.py`](file:///F:/RepoNeedle/research/stage3_15/validate_contextbench.py) | Tested across missing directory (exit 2), checksum mismatch (exit 3), malformed schema (exit 4). Exits with non-zero status. | **VERIFIED & COMPLIANT** |
| **Surface of Missing Predictions** | [`research/stage3_15/contextbench_adapter.py`](file:///F:/RepoNeedle/research/stage3_15/contextbench_adapter.py) | `compute_instance_metrics` assigns 0.0 to all metrics and records `FAILED_EMPTY_PREDICTIONS` if rankings are empty or truncated. | **VERIFIED & COMPLIANT** |
| **Preregistered Configuration Registry** | `FrozenConfigurationRegistry` in `contextbench_adapter.py` | `CONFIG-01`, `CONFIG-09`, and `CONFIG-10` instantiate canonical frozen factory methods (`bm25_baseline()`, `config_09()`, `config_10(50)`). Zero parameter tuning permitted. | **VERIFIED & COMPLIANT** |
| **Candidate Isolation** | `reponeedle/models.py` | Candidate F is implemented as an explicit, separate method (`AblationConfig.candidate_f()`), leaving frozen Candidate C (`candidate_c()`) immutable. | **VERIFIED & COMPLIANT** |
| **Prohibition of Network Workarounds** | `ACQUISITION_ATTEMPTS.json` | Network boundary honored without bypasses. ContextBench status maintained as `BLOCKED / PRELIMINARY` (`BLOCKED — DATA ACCESS`). | **VERIFIED & COMPLIANT** |

---

## 3. Configuration Integrity Assertion

Inspection of `reponeedle/models.py` confirms the architectural boundaries between frozen and active candidates:

1. **Frozen Baseline Candidate C** (`AblationConfig.candidate_c()`):
   - Tagged at `stage3-candidate-freeze` (`cd7f3b0`).
   - Skeletons enabled, doc filter penalty $0.5\times$, coupled BM25 symbols, static PageRank fusion.
   - Remains completely unchanged.
2. **Invalidated Candidate F** (`AblationConfig.candidate_f()`):
   - Polyglot symbols enabled, manifest-aware graph resolution, unbounded graph diffusion.
   - Preserved as an isolated historical candidate for reproducibility and auditability.
3. **Current Active Canonical Configurations**:
   - `CONFIG-01` (`BASE-BM25`): Pure Okapi BM25 baseline.
   - `CONFIG-09`: Decoupled lexical-subword hybrid quality winner (No PR).
   - `CONFIG-10`: Sparse Top-50 cascaded production reranker.

Neither Candidate F nor Candidate C modifies or pollutes the pre-registered configurations `CONFIG-01`, `CONFIG-09`, or `CONFIG-10`.
