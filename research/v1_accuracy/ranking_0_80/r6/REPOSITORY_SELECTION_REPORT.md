# RepoNeedle — Phase R6: Independent Repository Selection Report

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R6 — Independent Benchmark & Generalization Research  
**Author**: Benchmark Architect & Information Retrieval Researcher  
**Date**: November 2, 2026  
**Status**: Formal Repository Selection Specification  

---

## 1. Executive Summary

To evaluate whether RepoNeedle's ranking enhancements generalize beyond the historical 25 repositories of Agent Retrieval Bench (ARB) v2, Phase R6 establishes an **independent benchmark cohort of 18 open-source repositories**.

Every selected repository satisfies strict inclusion criteria:
1. **Zero Prior Exposure**: 0.0% overlap with any of the 25 ARB repositories evaluated in Phases R1 through R5.
2. **Polyglot Representation**: 5 distinct programming languages spanning interpreted, compiled, garbage-collected, and memory-managed ecosystems (Python, TypeScript/JavaScript, Rust, Go, Java).
3. **Scale & Architectural Diversity**: Repositories range from compact utility packages (< 20 files) to expansive industrial monorepos (> 1,000 files), covering web frameworks, systems tools, machine learning pipelines, serialization libraries, and networking stacks.
4. **Open Source Licensing**: All repositories carry permissive open-source licenses (MIT, Apache-2.0, BSD-3-Clause).

---

## 2. Independent Repository Cohort Inventory ($N=18$)

| # | Repository Identifier | Language | Ecosystem | Architecture / Role | Scale (Est. Files) | Permissive License |
| :-: | :--- | :---: | :---: | :--- | :---: | :---: |
| 1 | `django/django` | Python | Web / Database | High-scale ORM & full-stack web framework | 1,400+ | BSD-3-Clause |
| 2 | `scikit-learn/scikit-learn` | Python / Cython | Data Science | Statistical learning estimators & pipelines | 950+ | BSD-3-Clause |
| 3 | `pallets/flask` | Python | Web Services | WSGI microframework & routing engine | 65+ | BSD-3-Clause |
| 4 | `psf/requests` | Python | Networking | HTTP client library & adapter architecture | 80+ | Apache-2.0 |
| 5 | `sympy/sympy` | Python | Mathematics | Computer algebra system & symbolic parser | 1,200+ | BSD-3-Clause |
| 6 | `matplotlib/matplotlib` | Python / C++ | Visualization | Plotting library & multi-backend renderer | 850+ | PSF / Custom |
| 7 | `psf/black` | Python | Dev Tools | Deterministic AST code formatter | 90+ | MIT |
| 8 | `marshmallow-code/marshmallow` | Python | Serialization | Object serialization & schema validation | 45+ | MIT |
| 9 | `facebook/jest` | TypeScript | Testing | Monorepo testing platform, runners, reporters | 650+ | MIT |
| 10 | `axios/axios` | JavaScript | Networking | Promise-based HTTP client for browser & Node.js | 75+ | MIT |
| 11 | `expressjs/express` | JavaScript | Web Services | Fast, minimalist Node.js web application framework | 55+ | MIT |
| 12 | `serde-rs/serde` | Rust | Systems / Data | Serialization framework with procedural macros | 120+ | MIT / Apache-2.0 |
| 13 | `BurntSushi/ripgrep` | Rust | Systems / CLI | High-performance line-oriented search engine | 110+ | MIT / Unlicense |
| 14 | `hyperium/hyper` | Rust | Networking | Fast, correct HTTP implementation in Rust | 160+ | MIT |
| 15 | `moby/moby` | Go | Infrastructure | Docker container engine & virtualization daemon | 1,800+ | Apache-2.0 |
| 16 | `fatih/color` | Go | CLI / Utilities | ANSI terminal color formatting library | 18+ | MIT |
| 17 | `google/guava` | Java | Core Libraries | Industrial Java collections, concurrency, graphs | 900+ | Apache-2.0 |
| 18 | `square/retrofit` | Java | Networking | Type-safe HTTP client & interface generator | 140+ | Apache-2.0 |

---

## 3. Disjoint Partitioning Strategy

In compliance with benchmark governance, the 18 repositories are partitioned into three **strictly repository-disjoint sets**:

### 3.1 New Training Partition (9 Repositories — 50.0% of cohort)
Used for feature discovery, edge precision calibration, and parameter fitting:
- `django/django` (Python — Large)
- `scikit-learn/scikit-learn` (Python — Large)
- `psf/requests` (Python — Medium)
- `marshmallow-code/marshmallow` (Python — Small)
- `facebook/jest` (TypeScript — Large)
- `expressjs/express` (JavaScript — Medium)
- `serde-rs/serde` (Rust — Medium)
- `fatih/color` (Go — Small)
- `square/retrofit` (Java — Medium)

### 3.2 New Validation Partition (4 Repositories — 22.2% of cohort)
Used for model selection, threshold tuning, and hypothesis testing ($H_1, H_2, H_3$):
- `pallets/flask` (Python — Medium)
- `matplotlib/matplotlib` (Python — Large)
- `axios/axios` (JavaScript — Medium)
- `BurntSushi/ripgrep` (Rust — Medium)

### 3.3 New Final Held-Out Partition (5 Repositories — 27.8% of cohort)
Completely sealed during all model development; unsealed once for final evaluation ($H_4$):
- `sympy/sympy` (Python — Large)
- `psf/black` (Python — Medium)
- `hyperium/hyper` (Rust — Medium)
- `moby/moby` (Go — Large)
- `google/guava` (Java — Large)

---

## 4. Rigorous Overlap Audit vs ARB v2

Every candidate was verified against the 25 ARB v2 repositories:
`gin-gonic/gin`, `etcd-io/etcd`, `pallets/click`, `caddyserver/caddy`, `clap-rs/clap`, `spring-projects/spring-boot`, `vuejs/core`, `pypa/pip`, `fastapi/fastapi`, `scrapy/scrapy`, `ipython/ipython`, `tox-dev/tox`, `mockito/mockito`, `HypothesisWorks/hypothesis`, `numpy/numpy`, `tokio-rs/tokio`, `huggingface/diffusers`, `microsoft/playwright`, `pydantic/pydantic`, `eslint/eslint`, `huggingface/transformers`, `vitejs/vite`, `pytest-dev/pytest`, `astral-sh/ruff`, `python/mypy`.

### Audit Result:
- **Total Selected Repositories**: 18
- **Overlapping Repositories**: 0 (**0.0%**)
- **Disjointness Factor**: **100.0% Verified**
- **Prior Query Exposure**: **0 queries**
- **Prior Commit Exposure**: **0 commits**

