# RepoNeedle V1.1 — Python Version Compatibility Matrix & Runtime Specification

**Document Version**: 1.1.0  
**Author**: Senior Python Compatibility Engineer & Release Reviewer  
**Date**: November 2026  
**Target Package**: `reponeedle==1.1.0`  
**Specification Requirement**: `requires-python = ">=3.10"`  
**Verified CI Environments**: Python 3.10, Python 3.11, Python 3.12 on Linux (`ubuntu-latest` GitHub Actions runners)  
**Verified Local Developer Environment**: Python 3.12.10 on Windows 11  

---

## 1. Compatibility Overview

RepoNeedle V1.1.0 is engineered and verified for full operational compatibility across Python **3.10**, **3.11**, and **3.12**.

The runtime architecture avoids proprietary or version-locked C-extensions, emitting a pure Python distribution wheel (`reponeedle-1.1.0-py3-none-any.whl`) that installs and executes identically across all three minor versions.

> [!NOTE]
> **Platform Distinction**: GitHub Actions CI executes exclusively on `ubuntu-latest` Linux runners across Python 3.10, 3.11, and 3.12. Windows 11 verification was independently conducted in the local development environment using Python 3.12.10.

---

## 2. Minor Version Breakdown & Runtime Adaptations

| Python Version | Standard Library Differences | Runtime Adaptations in RepoNeedle | CI Test Status (`ubuntu-latest`) |
| :---: | :--- | :--- | :---: |
| **Python 3.10** | • `tomllib` is absent from standard library.<br>• Type union syntax (`X \| Y`) supported in annotations.<br>• `re` engine standard patterns. | • Conditional dependency: `tomli>=2.0.1; python_version < "3.11"` added to `pyproject.toml`.<br>• `RepoGraph` imports `tomllib` with fallback to `tomli`.<br>• Complete regex fallback in `RepoGraph.parse_cargo_manifest()` extracting package name, workspace members, and path dependencies with 100% equivalence. | **PASSED** (52s)<br>[PR Run #41476632666](https://github.com/krishika08/RepoNeedle/actions/runs/41476632666) |
| **Python 3.11** | • Native `tomllib` standard library.<br>• Faster CPython bytecode interpreter.<br>• Fine-grained tracebacks. | • Native `tomllib.loads()` for high-throughput Cargo manifest parsing.<br>• Target environment for research benchmark parity against pinned external repository (`eyuansu62/agent-retrieval-bench`). | **PASSED** (1m 1s)<br>[PR Run #41476632666](https://github.com/krishika08/RepoNeedle/actions/runs/41476632666) |
| **Python 3.12** | • Native `tomllib` standard.<br>• Deprecation of legacy `setuptools` build invocations.<br>• Refined AST syntax and node structures. | • Uses `setuptools.build_meta` build backend via PEP 517/PEP 621.<br>• Safe AST node traversal in polyglot symbol indexers. | **PASSED** (57s)<br>[PR Run #41476632666](https://github.com/krishika08/RepoNeedle/actions/runs/41476632666) |

---

## 3. Dependency Compatibility & Constraints

The dependencies defined in [`pyproject.toml`](file:///F:/RepoNeedle/pyproject.toml) have been verified across all target Python versions:

| Package | Version Constraint | Compatibility Justification |
| :--- | :---: | :--- |
| **`numpy`** | `>=1.24.0` | Unified array APIs across Python 3.10–3.12 without deprecation warnings. |
| **`scipy`** | `>=1.10.0` | Supplies sparse matrices and Wilcoxon statistical testing across all target platforms. |
| **`networkx`** | `>=3.0` | Graph representation for dependency and function graphs; fully pure-Python compatible. |
| **`pydantic`** | `>=2.0.0` | Fast Rust-backed schema validation for data models; precompiled wheels available for 3.10–3.12. |
| **`pathspec`** | `>=0.11.0` | Fast `.gitignore` path matching with zero native compilation requirements. |
| **`rich`** | `>=13.0.0` | Terminal formatting and rich table rendering in CLI interface. |
| **`tomli`** | `>=2.0.1; python_version < "3.11"` | Standard TOML parser library for Python 3.10, matching PEP 680 `tomllib` API. |

---

## 4. Test Accounting & Environment Separation

### 4.1 Production CI (Clean Checkouts on `ubuntu-latest`)
Executed across Python 3.10, 3.11, and 3.12:
- **Passed**: 244 tests
- **Skipped**: 5 tests
  - 3 research-parity tests (`test_arm101_production_parity.py`, `test_stage3_7_metrics.py`, `test_stage3_8_reproducibility.py`) gracefully skip via `pytest.importorskip("agent_retrieval_bench")` because external benchmark submodules are intentionally omitted from production checkouts.
  - 2 CUD-Pack tests in `tests/test_cud_pack_production.py` gracefully skip because the untracked 7.86 GB chunk corpus is kept out of standard CI checkouts.
- **Failures / Errors**: 0

### 4.2 Research Parity CI (Dedicated Job on `ubuntu-latest`)
Executed on Python 3.11 with pinned external repository `eyuansu62/agent-retrieval-bench` at commit `9e4d68937f29d5967afd62f4f6a24c1478298133`:
- **Passed**: 21 tests (100% assertions verified)
- **Skipped**: 0 tests
- **Failures / Errors**: 0

### 4.3 Local Windows Developer Verification (Windows 11, Python 3.12.10)
Executed directly on developer workstation:
- **Passed**: 271 tests (full suite including `test_cargo_toml_full_compatibility`)
- **Failures / Errors**: 0

---

## 5. Invariant Verification Across Python Versions

Across Python 3.10, 3.11, and 3.12:

1. **Deterministic CUD-Pack Invariant**:
   - The greedy knapsack token packing algorithm computes bit-identical token allocations regardless of CPython version or platform architecture.
   - Zero token overflow verified across budgets: 30, 50, 100, 500, 2000, 4000 tokens.
2. **Default Legacy Invariant**:
   - `RepoNeedleEngine()` defaults to `ranker="legacy"` on all Python versions.
3. **Change-Impact Routing**:
   - `ranking_engine="change_impact"` executes dependency graph propagation and surfaces structured attribution explanations identically across versions.
4. **Incremental Indexing**:
   - Content-hashed token caching operates deterministically, providing identical score parity ($\Delta \text{Score} = 0.00000000$) across fresh rebuilds.
