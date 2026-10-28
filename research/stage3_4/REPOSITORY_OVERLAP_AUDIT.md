# REPONEEDLE STAGE 3.4: COMPREHENSIVE REPOSITORY OVERLAP AND PARTITION AUDIT

**Document ID**: `STAGE3.4-OVERLAP-001`  
**Date**: 2026-10-28  
**Scope**: Full Lifecycle Repository Accounting, Contamination Identification, and Re-Audited Three-Way Partition  

---

## 1. Executive Summary

To prevent data leakage by familiarity, every source code repository referenced across all project phases—Stage 1 development, Stage 2 ablations, Stage 3 independent generalization, and unit tests—has been systematically re-audited.

The key finding of this re-audit is that `pallets/flask` and `psf/requests`, previously categorized as held-out in Stage 3.3, were directly utilized in `benchmarks/data/generator.py` and `tests/test_router.py` during Stage 1. Consequently, both have been reclassified into the **Replication & Development Partition**, leaving **12 clean, genuinely held-out repositories**.

---

## 2. Comprehensive Repository Lifecycle Cross-Reference

| Repository Name | Primary Language | Project Exposure Points | Prior Role in Development / Tuning | Final Re-Audited Classification |
| :--- | :---: | :--- | :--- | :--- |
| **`django/django`** | Python | Stage 3 Micro-Suite | None (SWE-bench Lite only) | **Category A: Genuinely Held-Out** |
| **`sympy/sympy`** | Python | Stage 3 Micro-Suite | None (SWE-bench Lite only) | **Category A: Genuinely Held-Out** |
| **`scikit-learn/scikit-learn`** | Python | Stage 3 Micro-Suite | None (SWE-bench Lite only) | **Category A: Genuinely Held-Out** |
| **`astropy/astropy`** | Python | Stage 3 Micro-Suite | None (SWE-bench Lite only) | **Category A: Genuinely Held-Out** |
| **`matplotlib/matplotlib`** | Python | Stage 3 Micro-Suite | None (SWE-bench Lite only) | **Category A: Genuinely Held-Out** |
| **`sphinx-doc/sphinx`** | Python | Stage 3 Micro-Suite | None (SWE-bench Lite only) | **Category A: Genuinely Held-Out** |
| **`mwaskom/seaborn`** | Python | Stage 3 Micro-Suite | None (SWE-bench Lite only) | **Category A: Genuinely Held-Out** |
| **`pydata/xarray`** | Python | Stage 3 Micro-Suite | None (SWE-bench Lite only) | **Category A: Genuinely Held-Out** |
| **`google/guava`** | Java | Stage 3 Micro-Suite | None (SWE-bench Multilingual only) | **Category A: Genuinely Held-Out** |
| **`facebook/react`** | TypeScript | Stage 3 Micro-Suite | None (SWE-bench Multilingual only) | **Category A: Genuinely Held-Out** |
| **`golang/go`** | Go | Stage 3 Micro-Suite | None (SWE-bench Multilingual only) | **Category A: Genuinely Held-Out** |
| **`BurntSushi/ripgrep`** | Rust | Stage 3 Micro-Suite | None (SWE-bench Multilingual only) | **Category A: Genuinely Held-Out** |
| **`pallets/flask`** | Python | Stage 1 Bench, Stage 3.3 | **Stage 1 Generator (`build_flask_corpus`), Router Unit Tests (`test_router.py`), Tokenizer Tests** | **Category B: Replication / Dev (RECLASSIFIED)** |
| **`psf/requests`** | Python | Stage 1 Bench, Stage 3.3 | **Stage 1 Generator (`build_requests_corpus`), Release Audit** | **Category B: Replication / Dev (RECLASSIFIED)** |
| **`pytest-dev/pytest`** | Python | ARB v2, Stage 2, Stage 3 | ARB positive tasks (`testlog2code`, `trace2code`, `code2test`) | **Category B: Replication / Dev** |
| **`gin-gonic/gin`** | Go | ARB v2, Stage 2, Stage 3 | ARB tasks, Stage 2 PageRank graph diffusion tuning | **Category B: Replication / Dev** |
| **`tokio-rs/tokio`** | Rust | ARB v2, Stage 2, Stage 3 | ARB tasks, Stage 2 Rust AST symbol parsing verification | **Category B: Replication / Dev** |
| **`vitejs/vite`** | TypeScript | ARB v2, Stage 2, Stage 3 | ARB positive tasks (`testlog2code`, `comment2context`) | **Category B: Replication / Dev** |
| **`spring-projects/spring-boot`** | Java | ARB v2, Stage 2, Stage 3 | ARB positive tasks (`testlog2code`, `trace2code`) | **Category B: Replication / Dev** |
| **`fastapi/fastapi`** | Python | ARB v2, Stage 1 Bench | Stage 1 generator (`build_fastapi_held_out_corpus`), ARB tasks | **Category B: Replication / Dev** |
| **`etcd-io/etcd`** | Go | ARB v2 | ARB positive tasks (`testlog2code`, `trace2code`) | **Category B: Replication / Dev** |
| **`huggingface/transformers`** | Python | ARB v2 | ARB positive tasks (`comment2context`, `code2test`) | **Category B: Replication / Dev** |
| **`huggingface/diffusers`** | Python | ARB v2 | ARB positive tasks (`testlog2code`, `code2test`) | **Category B: Replication / Dev** |
| **`clap-rs/clap`** | Rust | ARB v2, Stage 2 | Stage 2 Rust AST symbol extraction diagnostics | **Category B: Replication / Dev** |
| **`astral-sh/ruff`** | Rust | Stage 2 Diagnostics | Stage 2 Rust regex symbol extraction coverage testing | **Category B: Replication / Dev** |
| **`mockito/mockito`** | Java | ARB v2 | ARB positive tasks (`testlog2code`, `code2test`) | **Category B: Replication / Dev** |
| **`vuejs/core`** | TypeScript | ARB v2 | ARB positive tasks (`comment2context`, `code2test`) | **Category B: Replication / Dev** |
| **`pallets/click`** | Python | ARB v2, Stage 2/3 Profiling| Stage 2 runtime measurement, Stage 3 budget saturation profiling | **Category C: Excluded Profiling Codebase** |
| **`caddyserver/caddy`** | Go | ARB v2, Stage 2/3 Profiling| Stage 2/3 working set memory profiling | **Category C: Excluded Profiling Codebase** |

---

## 3. Explanatory Statement for Reclassified Repositories

### 3.1 Reclassification of `pallets/flask`
- **Initial Classification in Stage 3.3**: `HELD_OUT` (based on its origin in SWE-bench Lite).
- **Evidentiary Conflict**: Git history shows `pallets/flask` was used since the earliest commits of RepoNeedle. Specifically, `benchmarks/data/generator.py` defines `build_flask_corpus()` and five synthetic query samples. In addition, `tests/test_router.py` explicitly tests regex routing logic on `src/flask/app.py`.
- **Action**: Removed from Category A. Reassigned to Category B (`REPLICATION / DEVELOPMENT`).

### 3.2 Reclassification of `psf/requests`
- **Initial Classification in Stage 3.3**: `HELD_OUT` (based on its origin in SWE-bench Lite).
- **Evidentiary Conflict**: `benchmarks/data/generator.py` defines `build_requests_corpus()` and five development query instances.
- **Action**: Removed from Category A. Reassigned to Category B (`REPLICATION / DEVELOPMENT`).

---

## 4. Methodological Partitioning Rules Going Forward

1. **Category A (Genuinely Held-Out)**: Must strictly contain repositories with **zero** lines of code, test assertions, or diagnostic runs appearing in any prior development branch or report.
2. **Category B (Replication & Development)**: Contains all codebases that were used during development or tuning. Performance on Category B measures in-distribution regression and reproducibility, **never** independent generalization.
3. **Category C (Excluded Profiling)**: Repositories used for stress-testing, heap profiling, and latency benchmarking under memory measurement tools.
