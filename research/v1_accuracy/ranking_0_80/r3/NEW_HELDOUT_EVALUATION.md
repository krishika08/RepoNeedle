# REPONEEDLE MISSION 0.80+ — PHASE R3
# DELIVERABLE 11: CONFIRMATION / HELD-OUT EVALUATION REPORT

**Author**: Principal Information Retrieval Engineer, ML Evaluation Architect  
**Date**: November 2, 2026  
**Status**: APPROVED & FROZEN  
**Target Milestone**: Phase R3 (AST Symbol Intelligence + BM25L Ranking)  

---

## 1. EVALUATION PROTOCOL & GOVERNANCE DISCLOSURE

The confirmation partition consists of 5 repositories comprising 75 queries:
- `huggingface/transformers` (36 queries)
- `vitejs/vite` (25 queries)
- `pytest-dev/pytest` (7 queries)
- `astral-sh/ruff` (6 queries)
- `python/mypy` (1 query)

### Governance Disclosure:
As declared in `R3_DATA_GOVERNANCE.md`, these repositories were previously evaluated during the Phase R2 release gate. While no R3 hyperparameters or intent grammar rules were fitted or tuned against them, they are not unobserved.

---

## 2. CONFIRMATION METRIC COMPARISON

| Metric | Treatment A (R2 Baseline) | Treatment I (Champion) | Delta (I vs A) | Relative Change |
| :--- | :---: | :---: | :---: | :---: |
| **MRR** | **0.2965** | 0.2835 | **-0.0129** | -4.35% |
| **Hit@1** | **17.33% (13)** | **17.33% (13)** | 0.00% | 0.0% |
| **Recall@5** | **0.4489** | 0.3644 | -0.0845 | -18.82% |
| **Recall@10** | **0.5222** | 0.4822 | -0.0400 | -7.66% |
| **Recall@20** | **0.5800** | 0.5711 | -0.0089 | -1.53% |
| **Full Candidate Recall** | **100.0% (113/113)** | **100.0% (113/113)** | 0.00% | 0.0% |

---

## 3. PER-REPOSITORY ERROR ANALYSIS

| Repository | Query Count | Treatment A MRR | Treatment I MRR | Delta MRR | Diagnostic Findings |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `huggingface/transformers` | 36 | 0.4032 | 0.3995 | -0.0037 | Preserved near parity; BM25L stabilized large model files |
| `vitejs/vite` | 25 | 0.1580 | 0.1573 | -0.0007 | Preserved near parity across complex TypeScript plugins |
| `pytest-dev/pytest` | 7 | 0.3937 | 0.3199 | -0.0738 | Framework self-testing conflict (explained below) |
| `astral-sh/ruff` | 6 | 0.1357 | 0.1073 | -0.0284 | Rust AST rules diverged from standard Python patterns |
| `python/mypy` | 1 | 0.2000 | 0.0667 | -0.1333 | Single-query variance in type-checker AST |

### 3.1 The Pytest Self-Testing Anomaly
In `pytest-dev/pytest`, the repository being searched is itself a test framework. Consequently:
- Internal framework modules frequently reside in paths like `testing/` or `_pytest/pytester.py`.
- Under the `implementation_seeking` routing rule, paths with substring `test` were penalized by factor $0.05$.
- In ordinary application repos (e.g. `etcd`, `gin`, `tokio`), this penalty was extremely effective (driving `trace2code` MRR to 0.7138). But in meta-testing frameworks like `pytest`, test harness utilities were falsely penalized.

---

## 4. CONCLUSION

The confirmation evaluation confirms the finding from `STATISTICAL_VALIDATION.md`:
While Treatment I achieved substantial improvements on Train (+0.0734) and Validation (+0.0153), it regressed slightly on the confirmation split (-0.0129). This prevents Treatment I from being declared an unqualified, universal promotion over Treatment E.

