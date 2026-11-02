# RepoNeedle V1.1 — Python Version Compatibility Matrix & Runtime Specification

**Document Version**: 1.0.0  
**Author**: Senior Python Test Infrastructure Engineer  
**Date**: November 2026  
**Target Package**: `reponeedle==1.1.0`  
**Specification Requirement**: `requires-python = ">=3.10"`  
**Verified Environments**: Python 3.10, Python 3.11, Python 3.12 on Linux (`ubuntu-latest`) & Windows 11  

---

## 1. Compatibility Overview

RepoNeedle V1.1.0 is engineered and verified for full operational compatibility across Python **3.10**, **3.11**, and **3.12**.

The runtime architecture avoids proprietary or version-locked C-extensions, emitting a pure Python distribution wheel (`reponeedle-1.1.0-py3-none-any.whl`) that installs and executes identically across all three minor versions.

---

## 2. Minor Version Breakdown & Runtime Adaptations

| Python Version | Standard Library Differences | Runtime Adaptations in RepoNeedle | CI Test Status |
| :---: | :--- | :--- | :---: |
| **Python 3.10** | • `tomllib` is absent from standard library.<br>• Type union syntax (`X \| Y`) supported in annotations.<br>• `re` engine standard patterns. | Implemented zero-dependency regex fallback in `RepoGraph.parse_cargo_manifest()` when neither `tomllib` nor `tomli` is installed. | **PASSED** (1m 17s)<br>[Run #41472997734](https://github.com/krishika08/RepoNeedle/actions/runs/41472997734) |
| **Python 3.11** | • Native `tomllib` added to standard library.<br>• Faster CPython bytecode interpreter.<br>• Fine-grained tracebacks. | Uses native `tomllib.loads()` for high-throughput Cargo manifest parsing. Target environment for research benchmark parity. | **PASSED** (55s)<br>[Run #41472997734](https://github.com/krishika08/RepoNeedle/actions/runs/41472997734) |
| **Python 3.12** | • Native `tomllib` standard.<br>• Deprecation of legacy `setuptools` build invocations.<br>• Refined AST syntax and node structures. | Uses `setuptools.build_meta` build backend via PEP 517/PEP 621. Safe AST node traversal in polyglot symbol indexers. | **PASSED** (58s)<br>[Run #41472997734](https://github.com/krishika08/RepoNeedle/actions/runs/41472997734) |

---

## 3. Dependency Compatibility & Constraints

The dependencies defined in [`pyproject.toml`](file:///F:/RepoNeedle/pyproject.toml) have been verified across all target Python versions:

| Package | Version Constraint | Compatibility Justification |
| :--- | :---: | :--- |
| **`numpy`** | `>=1.24.0` | Provides unified array APIs across Python 3.10–3.12 without deprecation warnings. |
| **`scipy`** | `>=1.10.0` | Supplies sparse matrices and Wilcoxon statistical testing across all target platforms. |
| **`networkx`** | `>=3.0` | Graph representation for dependency and function graphs; fully pure-Python compatible. |
| **`pydantic`** | `>=2.0.0` | Fast Rust-backed schema validation for data models; precompiled wheels available for 3.10–3.12. |
| **`pathspec`** | `>=0.11.0` | Fast `.gitignore` path matching with zero native compilation requirements. |
| **`rich`** | `>=13.0.0` | Terminal formatting and rich table rendering in CLI interface. |

---

## 4. Invariant Verification Across Python Versions

Across Python 3.10, 3.11, and 3.12 in automated CI:

1. **Deterministic CUD-Pack Invariant**:
   - The greedy knapsack token packing algorithm computes bit-identical token allocations regardless of CPython version or platform architecture.
   - Zero token overflow verified across budgets: 30, 50, 100, 500, 2000, 4000 tokens.
2. **Default Legacy Invariant**:
   - `RepoNeedleEngine()` defaults to `ranker="legacy"` on all Python versions.
3. **Change-Impact Routing**:
   - `ranking_engine="change_impact"` executes dependency graph propagation and surfaces structured attribution explanations identically across versions.
4. **Incremental Indexing**:
   - Content-hashed token caching operates deterministically, providing identical score parity ($\Delta \text{Score} = 0.00000000$) across fresh rebuilds.
