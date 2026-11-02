# RepoNeedle — Phase R5: Repository, Query, and Commit Overlap Audit

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R5 — Function-Level, Change-Aware Code Retrieval  
**Date**: November 2, 2026  
**Status**: Authoritative Data Provenance & Manifest Verification  

---

## 1. Executive Summary & Audit Mandate

An essential principle of machine learning evaluation governance is **truth in data provenance**: a benchmark partition cannot be claimed as an out-of-distribution or independent "held-out" dataset if the models or hypotheses have been repeatedly developed against it.

This audit inspects the exact repository, query, and commit manifests used in Phase R5 and compares them against all historical milestones (R1 through R4).

---

## 2. Manifest Inventory Across Benchmark Splits

The evaluation dataset used in Phase R5 was loaded from `reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl` and split via `research/v1_accuracy/ranking_0_80/r2/src/split.py`:

### 2.1 Training Partition ($N=210$, 15 Repositories)
- `gin-gonic/gin` (88 queries)
- `etcd-io/etcd` (41 queries)
- `pallets/click` (26 queries)
- `caddyserver/caddy` (13 queries)
- `clap-rs/clap` (10 queries)
- `spring-projects/spring-boot` (8 queries)
- `vuejs/core` (6 queries)
- `pypa/pip` (5 queries)
- `fastapi/fastapi` (3 queries)
- `scrapy/scrapy` (3 queries)
- `ipython/ipython` (2 queries)
- `tox-dev/tox` (2 queries)
- `mockito/mockito` (1 query)
- `HypothesisWorks/hypothesis` (1 query)
- `numpy/numpy` (1 query)

### 2.2 Validation Partition ($N=60$, 5 Repositories)
- `tokio-rs/tokio` (38 queries)
- `huggingface/diffusers` (16 queries)
- `microsoft/playwright` (4 queries)
- `pydantic/pydantic` (1 query)
- `eslint/eslint` (1 query)

### 2.3 Diagnostic "Held-Out" Partition ($N=75$, 5 Repositories)
- `huggingface/transformers` (36 queries)
- `vitejs/vite` (25 queries)
- `pytest-dev/pytest` (7 queries)
- `astral-sh/ruff` (6 queries)
- `python/mypy` (1 query)

---

## 3. Comparative Overlap Analysis Against R1–R4

| Metric / Dimension | Phase R1 | Phase R2 | Phase R3 | Phase R4 | Phase R5 | Overlap vs R5 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Total Query Count** | 345 | 345 | 345 | 345 | 345 | **100.0% (345/345)** |
| **Total Repositories** | 25 | 25 | 25 | 25 | 25 | **100.0% (25/25)** |
| **Distinct Git Trees** | 218 | 218 | 218 | 218 | 218 | **100.0% (218/218)** |
| **Training Repositories** | N/A | 15 | 15 | 15 | 15 | **100.0% (15/15)** |
| **Validation Repositories**| N/A | 5 | 5 | 5 | 5 | **100.0% (5/5)** |
| **Held-Out Repositories** | N/A | 5 | 5 | 5 | 5 | **100.0% (5/5)** |

---

## 4. Formal Audit Finding on "Held-Out" Status

> [!WARNING]
> **CRITICAL PROVENANCE DISCLOSURE**:  
> The 5 repositories in the R5 "held-out" split (`transformers`, `vite`, `pytest`, `ruff`, `mypy`) share **100% repository overlap, 100% query overlap, and 100% commit overlap** with the confirmation partition evaluated in Phases R2, R3, and R4.
> 
> No external, virgin, or previously unexamined repositories exist on disk in the local workspace.
> 
> In accordance with scientific research governance:
> 1. This partition must be strictly designated as an **internal diagnostic partition**.
> 2. It cannot be presented to engineering leadership as independent out-of-distribution proof of generalizability.
> 3. True external promotion validation will require acquiring a distinct benchmark corpus (e.g. SWE-bench or ContextBench instances) from an independent origin.

