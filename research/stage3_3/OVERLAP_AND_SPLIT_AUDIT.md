# REPONEEDLE STAGE 3.3: DATASET OVERLAP AND REPOSITORY PARTITION AUDIT

**Document ID**: `STAGE3.3-OVERLAP-001`  
**Date**: 2026-10-28  
**Scope**: Systematic Forensic Cross-Referencing of ContextBench Repositories, ARB v2, Stage 2 Ablations, and Prior Micro-Evaluations  

---

## 1. Executive Summary

A critical scientific vulnerability in machine learning evaluation is "leakage by familiarity"—evaluating an algorithm on repositories or task structures that were directly or indirectly used to guide feature design, hyperparameter selection, or router tuning.

A benchmark having a different name (e.g. *ContextBench* vs *Agent Retrieval Benchmark*) does not confer statistical independence if the underlying source code repositories or task formulations overlap.

This audit establishes an exhaustive cross-reference across all evaluation datasets used throughout the RepoNeedle research lifecycle.

---

## 2. Inventory of Historical Evaluation & Development Corpora

| Lifecycle Stage | Benchmark / Dataset Name | Repositories Included | Task Count | Purpose & Usage |
| :--- | :--- | :--- | :---: | :--- |
| **Stage 1 (Baseline)** | ARB v2 (Agent Retrieval Bench) | 12 repositories (6 Python, 2 TS, 2 Java, 2 Go, 2 Rust) | 427 samples (345 positive, 82 selective) | Initial performance baseline, autonomous router tuning, release v0.1.0 |
| **Stage 2 (Ablations)** | ARB v2 + Diagnostic Corpora | 12 ARB repos + `pallets/click` + `caddyserver/caddy` | 32 factorial configs $\times$ 345 samples | Factorial ablation matrix, PPR damping tuning, doc filtering weights |
| **Stage 3.1 & 3.2** | ContextBench-Derived Micro-Suite | 14 Held-out + 5 Replication repos | 19 micro-tasks | First attempted independent generalization test; revealed budget unsaturated |
| **Stage 3.3 (Target)** | Official ContextBench (`default` / `verified`) | 66 repositories (documented) | 1,136 tasks (500 verified) | Authoritative independent generalization target |

---

## 3. Repository Overlap Cross-Reference Matrix

The 66 repositories documented in ContextBench and SWE-bench Multilingual are partitioned into three mutually exclusive scientific categories:

### Category A: Genuinely Held-Out Repositories
*Criteria*: Zero prior exposure in ARB v2, Stage 1 tuning, or Stage 2 component ablations. Safe for independent generalization claims.

1. `django/django` (Python - SWE-bench Lite)
2. `sympy/sympy` (Python - SWE-bench Lite)
3. `scikit-learn/scikit-learn` (Python - SWE-bench Lite)
4. `astropy/astropy` (Python - SWE-bench Lite)
5. `matplotlib/matplotlib` (Python - SWE-bench Lite)
6. `sphinx-doc/sphinx` (Python - SWE-bench Lite)
7. `psf/requests` (Python - SWE-bench Lite)
8. `mwaskom/seaborn` (Python - SWE-bench Lite)
9. `pydata/xarray` (Python - SWE-bench Lite)
10. `pallets/flask` (Python - SWE-bench Lite)
11. `pylint-dev/pylint` (Python - SWE-bench Lite)
12. `google/guava` (Java - SWE-bench Multilingual)
13. `facebook/react` (TypeScript / JavaScript)
14. `golang/go` (Go - Standard library runtime)
15. `BurntSushi/ripgrep` (Rust - Modular CLI)
16. *Additional 37 held-out repos documented in ContextBench full split*

### Category B: Replication Repositories (Development Overlap)
*Criteria*: Codebases present in ARB v2 or Stage 2 diagnostics. Performance on these repositories measures *in-distribution regression / replication*, NOT independent generalization.

1. **`pytest-dev/pytest`**: Heavily utilized in ARB v2 (`testlog2code`, `trace2code`, `code2test`). Also present in SWE-bench Lite and ContextBench. **OVERLAP: HIGH**.
2. **`gin-gonic/gin`**: Present in ARB v2; used for Stage 2 Personalized PageRank graph diffusion parameter tuning. **OVERLAP: HIGH**.
3. **`tokio-rs/tokio`**: Present in ARB v2; used for Stage 2 Rust symbol extraction and AST parsing verification. **OVERLAP: HIGH**.
4. **`vitejs/vite`**: Present in ARB v2 (`testlog2code`, `comment2context`). **OVERLAP: HIGH**.
5. **`spring-projects/spring-boot`**: Present in ARB v2 (`testlog2code`, `trace2code`). **OVERLAP: HIGH**.
6. **`etcd-io/etcd`**: Present in ARB v2. **OVERLAP: HIGH**.
7. **`fastapi/fastapi`**: Present in ARB v2. **OVERLAP: HIGH**.
8. **`huggingface/transformers`**: Present in ARB v2. **OVERLAP: HIGH**.
9. **`huggingface/diffusers`**: Present in ARB v2. **OVERLAP: HIGH**.
10. **`clap-rs/clap`**: Present in ARB v2. **OVERLAP: HIGH**.
11. **`mockito/mockito`**: Present in ARB v2. **OVERLAP: HIGH**.
12. **`vuejs/core`**: Present in ARB v2. **OVERLAP: HIGH**.

### Category C: Excluded Tasks & Profiling Codebases
*Criteria*: Codebases used for runtime resource profiling or tasks lacking reproducible provenance.

1. **`pallets/click`**: Utilized in Stage 2/Stage 3 runtime and memory profiling. Excluded from held-out claims; reserved for resource profiling.
2. **`caddyserver/caddy`**: Utilized in Stage 2/Stage 3 memory profiling. Excluded from held-out claims.
3. **Unverified micro-instances without full AST snapshots**: Any task where candidate files cannot be unambiguously extracted from a frozen git tree is excluded.

---

## 4. Partitioning Policy for Future Stage 3.x Evaluations

1. **Strict Partition Segregation**: No metric combining Category A (Held-Out) and Category B (Replication) into a single aggregate score may ever be reported as an "independent benchmark score."
2. **Pre-Registered Rule Application**: Decision Rules 1 and 2 (statistical significance $\Delta > 0$ and $\ge +5\%$ relative gain) must be calculated **exclusively on Category A**. Category B may only be reported as a secondary replication check.
3. **Audit Trail**: Every evaluated sample must carry its repository provenance and partition label in all raw JSONL and CSV output files.
