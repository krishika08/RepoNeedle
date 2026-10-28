# REPONEEDLE STAGE 3.4: EVIDENCE INTEGRITY AND RETRIEVAL BENCHMARK AUDIT

**Document ID**: `STAGE3.4-EVIDENCE-001`  
**Date**: 2026-10-28  
**Scope**: Forensic Audit of Evaluation Claims, Benchmark Scale Discrepancies, Repository Overlap Corrections, and Statistical Recalibration  
**Status**: **PRELIMINARY / DEVELOPMENT EVIDENCE ONLY**  

---

## 1. Executive Summary & Narrative Correction

Rigorous scientific standards require correcting over-generalized claims, identifying hidden data leakage, and distinguishing small diagnostic fixtures from authoritative benchmark evaluations.

### Critical Evidence Corrections:
1. **The 19-Task Micro-Benchmark Is Diagnostic Only**:
   - The micro-suite used in Stages 3.1–3.3 contains only 19 task instances across 19 repositories.
   - Each micro-fixture contains only 2 to 5 files, with total token counts under 450 tokens ($450 \ll 8,000$). Under an 8,000-token prompt budget, the complete repository snapshot fit with zero budget saturation, leaving skeleton compression, documentation filtering, and candidate eviction completely unexercised.
   - **Correction**: These results are formally classified as **small-fixture diagnostic evidence**. They must never be described as full ContextBench validation or used to establish general retrieval superiority.
2. **Reclassification of `pallets/flask` and `psf/requests`**:
   - A forensic code audit of `benchmarks/data/generator.py`, `tests/test_router.py`, `tests/test_tokenizer.py`, and `data_provenance/PROVENANCE.md` revealed that `pallets/flask` and `psf/requests` were part of RepoNeedle's primary Stage 1 development suite (`RepoNeedle-Bench`).
   - Router heuristics were explicitly tested against Flask stack traces (`src/flask/app.py`), and tokenizer logic was tested on Flask paths (`src/flask/sessions.py`).
   - **Correction**: `pallets/flask` and `psf/requests` are formally stripped of "Held-Out" status and reassigned to the **Development / Replication Partition**.
3. **Recomputed Statistics on Clean Held-Out Partition ($N=12$)**:
   - Recalibrating metrics on the 12 clean, eligible held-out repositories confirms that preregistered **Rule 1** (Bootstrap CI strictly $> 0$) and **Rule 2** (Relative gain $\ge +5.0\%$) strictly **FAIL**.
4. **ARB v2 ($N=345$) Full-Corpus Evidence Scope**:
   - The 345 positive ARB samples across 25 full repositories represent **in-distribution development and regression evidence**, not independent generalization, because ARB guided development and ablation tuning.

---

## 2. Micro-Benchmark Discrepancy Accounting

| Dimension | Official ContextBench Benchmark | Stage 3.3 Micro-Evaluation Suite | Scientific Gap |
| :--- | :--- | :--- | :--- |
| **Total Task Count** | 1,136 tasks (`default`) / 500 (`verified`) | 19 task instances | $59.8\times$ fewer tasks than verified split |
| **Unique Repositories** | 66 codebases | 19 codebases (14 held-out, 5 replication) | Limited repository diversity |
| **Corpus Scale per Task** | Full Git repository snapshot (100–1,000+ files) | 2 to 5 curated files per task | Truncated synthetic fixtures |
| **Corpus Token Volume** | 20,000 to 500,000+ tokens | 180 to 440 tokens | Budget pressure is completely absent ($450 \ll 8,000$) |
| **Context Selection Test** | Requires aggressive candidate pruning | Every candidate file fits in full | Skeleton and doc filtering unexercised |
| **Formal Evidentiary Role** | Authoritative Independent Benchmark | **Small-Fixture Diagnostic Unit Test** | Cannot establish general superiority |

---

## 3. Forensic Contamination Audit: `pallets/flask` and `psf/requests`

An audit of the repository's commit history and development artifacts was conducted to verify repository independence:

### 3.1 Evidence of Prior Exposure for `pallets/flask`:
1. **`benchmarks/data/generator.py`**:
   - Lines 50–120 define `build_flask_corpus() -> List[FileDoc]`.
   - Five distinct benchmark samples were hardcoded:
     - `flask_trace2code_01` (Repo: `pallets/flask`, targets: `src/flask/wrappers.py`, `src/flask/app.py`)
     - `flask_code2test_01` (Repo: `pallets/flask`)
     - `flask_edit2ripple_01` (Repo: `pallets/flask`, target: `src/flask/ctx.py`)
     - `flask_comment2context_01` (Repo: `pallets/flask`, target: `src/flask/blueprints.py`)
     - `flask_selective_01` (Repo: `pallets/flask`)
2. **`data_provenance/PROVENANCE.md`**:
   - Formally lists `pallets/flask` as a core development benchmark codebase:
     `| pallets/flask | BSD-3-Clause | https://github.com/pallets/flask | trace2code, code2test, edit2ripple, comment2context, selective |`
3. **`tests/test_router.py`**:
   - Router classification unit tests directly test against Flask stack traces:
     `File "src/flask/app.py", line 28, in wsgi_app`
4. **`tests/test_tokenizer.py`**:
   - Tokenizer tests explicitly verify path splitting on Flask:
     `tokens = tokenizer.tokenize_path("src/flask/sessions.py")`

### 3.2 Evidence of Prior Exposure for `psf/requests`:
1. **`benchmarks/data/generator.py`**:
   - Lines 125–180 define `build_requests_corpus() -> List[FileDoc]`.
   - Five development samples hardcoded (`requests_trace2code_01` through `requests_selective_01`).
2. **`FINAL_RELEASE_AUDIT.md` & `HF_RELEASE_CHECKLIST.md`**:
   - Explicitly cite `psf/requests` as a foundation development codebase for `RepoNeedle-Bench`.

### 3.3 Reclassification Decision:
Classifying `pallets/flask` or `psf/requests` as "Held-Out" violated experimental segregation principles because both codebases directly shaped router thresholds, tokenizers, and baseline tuning. Both are formally reclassified as **Category B: Replication & Development Repositories**.

---

## 4. Recalibrated Statistics on Clean Held-Out Partition ($N=12$)

Excluding `pallets/flask` and `psf/requests` leaves $N=12$ genuinely held-out repositories:
1. `django/django` (Python)
2. `sympy/sympy` (Python)
3. `scikit-learn/scikit-learn` (Python)
4. `astropy/astropy` (Python)
5. `matplotlib/matplotlib` (Python)
6. `sphinx-doc/sphinx` (Python)
7. `mwaskom/seaborn` (Python)
8. `pydata/xarray` (Python)
9. `google/guava` (Java)
10. `facebook/react` (TypeScript)
11. `golang/go` (Go)
12. `BurntSushi/ripgrep` (Rust)

### Empirical Metrics Across Clean Held-Out Repositories ($N=12$, 8k Budget):

| System Configuration | File Recall@8k | File Precision@8k | File F1 | Separate MRR | BCY@8k | Recall@20 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **BASE-BM25** | 0.8750 | 0.6361 | 0.7063 | 0.9167 | 0.8762 | 0.9167 |
| **BASE-REPOMAP** | **1.0000** | **0.7194** | **0.8175** | 0.6250 | **1.0000** | **1.0000** |
| **CAND-A (Static Hybrid Full)** | 0.9167 | 0.6361 | 0.7341 | 0.9167 | 0.9167 | 0.9167 |
| **CAND-B (Candidate A + Skeletons)** | 0.9167 | 0.6361 | 0.7341 | 0.9167 | 0.9167 | 0.9167 |
| **CAND-C (Candidate B + Doc Filter)**| 0.9167 | 0.6361 | 0.7341 | 0.9167 | 0.9167 | 0.9167 |
| **CAND-D (Graph Diffusion)** | 0.9167 | 0.6361 | 0.7341 | 0.9167 | 0.9167 | 0.9167 |
| **CAND-E (Polyglot Symbols)** | 0.9167 | 0.6361 | 0.7341 | 0.9167 | 0.9167 | 0.9167 |

### Preregistered Decision Rule Audit on Clean Partition ($N=12$):

| Pre-Registered Rule | Required Threshold | Observed Empirical Value | Literal Decision Status |
| :--- | :--- | :--- | :--- |
| **Rule 1: Statistically Significant Gain** | 95% Clustered Bootstrap CI strictly $> 0$ vs BM25 | 95% CI = **[0.0000, +0.1250]** ($p = 0.3388$) | **FAILED** (Lower bound touches 0.0000) |
| **Rule 2: Minimum Relative Gain** | Relative Context Recall Gain $\ge +5.0\%$ vs BM25 | Relative Gain = **+4.76%** (0.9167 vs 0.8750) | **FAILED** (Below 5.0% threshold) |
| **Head-to-Head vs Pure BM25** | Paired breakdown | **1 Win** (`react`), **11 Ties**, **0 Losses** | Non-significant ($t=1.000$) |
| **Head-to-Head vs RepoMap** | Context Recall Comparison | Candidate C = **0.9167** vs RepoMap = **1.0000** | RepoMap dominates on Context Recall |

**Audit Conclusion**: Re-auditing and purifying the held-out partition solidifies the finding that independent retrieval generalization remains strictly **PRELIMINARY EVIDENCE ONLY**.
