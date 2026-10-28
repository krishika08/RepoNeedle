# REPONEEDLE STAGE 3 DATASET AND REPOSITORY OVERLAP AUDIT

**Document ID**: `STAGE3-OVERLAP-001`  
**Date**: 2026-10-28  
**Evaluator Scope**: ARB v2 (Dev) vs SWE-bench Lite vs ContextBench (Independent)  
**Partition Strategy**: Strict Repository-Level Boundary Separation  

---

## 1. Objective and Audit Standards

Under scientific evaluation principles, a dataset cannot be claimed as an independent holdout merely because its benchmark wrapper or name differs from the training/development suite. If a repository or its files were used for development, parameter tuning, or error analysis, evaluating on that repository measures **in-distribution replication**, not **independent generalization**.

This audit examines:
1. **Agent Retrieval Bench v2** (Our frozen development benchmark: 25 repositories, 427 samples).
2. **ContextBench** (`Contextbench/ContextBench`: 66 repositories, 8 languages, 1,136 tasks).
3. **SWE-bench Lite** (`princeton-nlp/SWE-bench_Lite`: 11 repositories, 300 instances).

---

## 2. Canonical Repository Inventory

### 2.1 ARB v2 Development & Tuning Repositories ($N=25$)
All 25 repositories below are classified as **DEVELOPMENT / IN-DISTRIBUTION**. They cannot be used for independent generalization claims:

1. `astral-sh/ruff` (Python/Rust, 6 samples)
2. `caddyserver/caddy` (Go, 13 samples)
3. `clap-rs/clap` (Rust, 10 samples)
4. `eslint/eslint` (TypeScript, 1 sample)
5. `etcd-io/etcd` (Go, 41 samples)
6. `fastapi/fastapi` (Python, 3 samples)
7. `gin-gonic/gin` (Go, 88 samples)
8. `huggingface/diffusers` (Python, 16 samples)
9. `huggingface/transformers` (Python, 36 samples)
10. `HypothesisWorks/hypothesis` (Python, 1 sample)
11. `ipython/ipython` (Python, 2 samples)
12. `microsoft/playwright` (TypeScript, 4 samples)
13. `mockito/mockito` (Java, 1 sample)
14. `numpy/numpy` (Python, 1 sample)
15. `pallets/click` (Python, 26 samples)
16. `pydantic/pydantic` (Python, 1 sample)
17. `pypa/pip` (Python, 5 samples)
18. `pytest-dev/pytest` (Python, 7 samples)
19. `python/mypy` (Python, 1 sample)
20. `scrapy/scrapy` (Python, 3 samples)
21. `spring-projects/spring-boot` (Java, 8 samples)
22. `tokio-rs/tokio` (Rust, 38 samples)
23. `tox-dev/tox` (Python, 2 samples)
24. `vitejs/vite` (TypeScript, 25 samples)
25. `vuejs/core` (TypeScript, 6 samples)

---

## 3. Independent Benchmark Overlap Cross-Tabulation

| Candidate Repository | Source Benchmark | Language | Overlaps ARB v2? | Partition Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **django/django** | SWE-bench Lite / ContextBench | Python | **NO** | **GENUINELY HELD-OUT TEST** | Zero prior exposure in RepoNeedle dev |
| **sympy/sympy** | SWE-bench Lite / ContextBench | Python | **NO** | **GENUINELY HELD-OUT TEST** | Zero prior exposure in RepoNeedle dev |
| **scikit-learn/scikit-learn** | SWE-bench Lite / ContextBench | Python | **NO** | **GENUINELY HELD-OUT TEST** | Zero prior exposure in RepoNeedle dev |
| **astropy/astropy** | SWE-bench Lite / ContextBench | Python | **NO** | **GENUINELY HELD-OUT TEST** | Zero prior exposure in RepoNeedle dev |
| **matplotlib/matplotlib** | SWE-bench Lite / ContextBench | Python | **NO** | **GENUINELY HELD-OUT TEST** | Zero prior exposure in RepoNeedle dev |
| **sphinx-doc/sphinx** | SWE-bench Lite / ContextBench | Python | **NO** | **GENUINELY HELD-OUT TEST** | Zero prior exposure in RepoNeedle dev |
| **psf/requests** | SWE-bench Lite / ContextBench | Python | **NO** | **GENUINELY HELD-OUT TEST** | Zero prior exposure in RepoNeedle dev |
| **mwaskom/seaborn** | SWE-bench Lite / ContextBench | Python | **NO** | **GENUINELY HELD-OUT TEST** | Zero prior exposure in RepoNeedle dev |
| **pydata/xarray** | SWE-bench Lite / ContextBench | Python | **NO** | **GENUINELY HELD-OUT TEST** | Zero prior exposure in RepoNeedle dev |
| **pallets/flask** | SWE-bench Lite / ContextBench | Python | **PARTIAL (Org)** | **GENUINELY HELD-OUT TEST** | Different repo from click; zero shared code |
| **pytest-dev/pytest** | SWE-bench Lite / ContextBench | Python | **YES** | **EXTERNAL REPLICATION ONLY** | Overlaps ARB v2; report separately |
| **google/guava** | ContextBench Polyglot | Java | **NO** | **GENUINELY HELD-OUT TEST** | Multi-SWE-bench Java holdout |
| **facebook/react** | ContextBench Polyglot | JavaScript | **NO** | **GENUINELY HELD-OUT TEST** | Multi-SWE-bench JS holdout |
| **golang/go** | ContextBench Polyglot | Go | **NO** | **GENUINELY HELD-OUT TEST** | Multi-SWE-bench Go holdout |
| **BurntSushi/ripgrep**| ContextBench Polyglot | Rust | **NO** | **GENUINELY HELD-OUT TEST** | Multi-SWE-bench Rust holdout |
| **gin-gonic/gin** | ContextBench Polyglot | Go | **YES** | **EXTERNAL REPLICATION ONLY** | Overlaps ARB v2; report separately |
| **tokio-rs/tokio** | ContextBench Polyglot | Rust | **YES** | **EXTERNAL REPLICATION ONLY** | Overlaps ARB v2; report separately |
| **vitejs/vite** | ContextBench Polyglot | TypeScript | **YES** | **EXTERNAL REPLICATION ONLY** | Overlaps ARB v2; report separately |
| **spring-projects/spring-boot**| ContextBench Polyglot | Java | **YES** | **EXTERNAL REPLICATION ONLY** | Overlaps ARB v2; report separately |

---

## 4. Formal Partitioning and Integrity Checksums

To prevent test-set leakage, all independent evaluation is strictly partitioned into two disjoint sets:

### Partition 1: Genuinely Held-Out Generalization Set (`PARTITION_HELD_OUT`)
- **Repositories**: `django/django`, `sympy/sympy`, `scikit-learn/scikit-learn`, `astropy/astropy`, `matplotlib/matplotlib`, `sphinx-doc/sphinx`, `psf/requests`, `mwaskom/seaborn`, `pydata/xarray`, `pallets/flask`, `google/guava`, `facebook/react`, `golang/go`, `BurntSushi/ripgrep`.
- **Purpose**: Primary evaluation gate for independent generalization.
- **Rule**: No candidate tuning or parameter selection may be performed on this set.

### Partition 2: External In-Distribution Replication Set (`PARTITION_REPLICATION`)
- **Repositories**: `pytest-dev/pytest`, `gin-gonic/gin`, `tokio-rs/tokio`, `vitejs/vite`, `spring-projects/spring-boot`.
- **Purpose**: Cross-benchmark validation to verify that findings replicate when task formulation changes on known codebases.
- **Rule**: Reported strictly in separate tables; excluded from generalization claims.

---

## 5. Frozen Partition Checksum Manifest

```json
{
  "partition_held_out_sha256": "8a71ef08412b1d6435bc299e2e28328731519d5c4146a8c4fa569a7428f5cda1",
  "partition_replication_sha256": "4b61834927cb89110b98a31e8b2bcf1b4f4946761596e2794ebf32b84a919b12",
  "total_held_out_repositories": 14,
  "total_replication_repositories": 5,
  "audit_verdict": "APPROVED_DISJOINT"
}
```

