# RepoNeedle Stage 3.9.3: Python-First LFCG Test Suite Report

> **Status:** PASSED (14/14 Unit Tests Passing; 249/249 Regression Tests Passing)  
> **Date:** 2026-11-01  
> **Component:** Lean Function Call Graph (LFCG) Python Prototype Engine  
> **Test File:** [`research/stage3_9/prototypes/test_python_lfcg.py`](file:///F:/RepoNeedle/research/stage3_9/prototypes/test_python_lfcg.py)  
> **Implementation File:** [`research/stage3_9/prototypes/python_lfcg.py`](file:///F:/RepoNeedle/research/stage3_9/prototypes/python_lfcg.py)  

---

## 1. Executive Summary

This report documents the verification and test execution of the compiler-grade Python Lean Function Call Graph (LFCG) prototype developed under **Stage 3.9.3 Phase D**.

The primary architectural mandate of LFCG is **fail-closed precision**: ensuring that call edges injected into the retrieval diffusion graph are syntactically exact or rigorously scoped, while ambiguous, external, or dynamic dispatch expressions resolve to `UNRESOLVED` (Tier E) with zero injected edges.

### Overall Verification Summary
- **Prototype Test Suite:** 14 passed in 0.08s (`pytest research/stage3_9/prototypes/test_python_lfcg.py`).
- **Core Production Regression Suite:** 249 passed in 5.73s (`pytest tests/`).
- **Crash Rate:** 0.0% (Zero crashes across malformed syntax, dynamic invocations, or deeply nested scopes).
- **Separation of Extraction vs. Resolution:** 100% verified (raw AST extractions are recorded independently from call resolution status).

---

## 2. Test Execution Matrix (13 Scenarios + Determinism)

| # | Test Function | Target Scenario | Expected Behavior | Observed Result | Status |
|---|---|---|---|---|:---:|
| 1 | `test_direct_local_calls` | Direct local function calls within file | Exact AST resolution to module function (`TIER_A_EXACT_AST`) | Resolved to `main.py#helper_target` | **PASS** |
| 2 | `test_imports_and_aliases` | Imports: direct, alias, `from ... import` | Scoped import tracking (`TIER_B_SCOPED_IMPORT`); aliases mapped to target name | `alias_compute` $\to$ `utils.py#compute_val` | **PASS** |
| 3 | `test_relative_imports` | Relative imports (`.` and `..`) | Multi-level package hierarchy directory resolution | `..helpers` resolved to `helpers.py#root_helper` | **PASS** |
| 4 | `test_nested_scopes` | Nested function definitions | Scope stack tracking (`scope_prefix`); inner caller resolved | `nested_worker` registered with `is_nested=True` | **PASS** |
| 5 | `test_function_shadowing` | Function shadowed by local variable | Fail-closed: marked `UNRESOLVED` (`shadowed_by_local_scope`) | Zero call edge injected for shadowed lambda | **PASS** |
| 6 | `test_methods_and_self_calls` | Methods and `self` calls | Receiver-bound resolution (`TIER_C_RECEIVER_BOUND`) to class method | `self.internal_action` $\to$ `Service.internal_action` | **PASS** |
| 7 | `test_unknown_receivers_never_exact` | Unknown receivers (`obj.method()`) | **Rule 8 Enforced**: refuse to guess exact target; marked `UNRESOLVED` | `external_obj.internal_action` $\to$ Tier E (`UNRESOLVED`) | **PASS** |
| 8 | `test_decorators_metadata` | Decorators on functions/methods | Decorators preserved as node metadata without altering identity | `@property` extracted into node `decorators` tuple | **PASS** |
| 9 | `test_recursive_calls` | Recursive function calls | Function resolving self-call to its own URI | Exact AST self-call resolution | **PASS** |
| 10 | `test_dynamic_dispatch` | Dynamic calls (`getattr`, `locals()()`) | Unresolvable dynamic call marked `UNRESOLVED` | Zero call edge injected | **PASS** |
| 11 | `test_builtins_filtered` | Python standard builtins (`len`, `print`) | Filtered out via `builtins` set | `len()` resolved to `builtin_filter` / `UNRESOLVED` | **PASS** |
| 12 | `test_external_libraries_unresolved` | External standard library & 3rd party | Filtered via unindexed module prefix (`math`, `os.path`) | `math.sqrt`, `os.path.join` $\to$ Tier E (`UNRESOLVED`) | **PASS** |
| 13 | `test_syntax_error_fail_closed` | Malformed source syntax | Safe catch; file registered; 0 functions/edges | Zero crashes; 0 edges emitted for syntax error file | **PASS** |
| 14 | `test_edge_types_and_determinism` | Graph schema & serialization | Only `CONTAINS` and `CALLS` edges; identical SHA-256 hash across runs | SHA-256 byte-for-byte identical; valid schema | **PASS** |

---

## 3. Detailed Scenario Analysis

### 3.1 Direct Local Calls and Nested Scopes (Scenarios 1 & 4)
- **Local Calls:** The engine tracks all top-level functions in `self.functions_by_file[file_uri]`. In `main.py`, `caller_local_and_nested` calls `helper_target()`. The resolver matches the lexical symbol in the same file module scope and assigns `TIER_A_EXACT_AST` with weight $W = 1.0$ and ambiguity penalty $\Omega = 1.0$.
- **Nested Scopes:** In `main.py`, `nested_worker` is defined inside `caller_local_and_nested`. The AST visitor maintains a `func_stack`. When entering `nested_worker`, it registers `is_nested=True` and scopes its URI as `func://...#caller_local_and_nested.nested_worker`. Calls from the outer function resolve exactly to this scoped URI.

### 3.2 Imports, Aliases, and Relative Imports (Scenarios 2 & 3)
- **Import Tracking:** During Pass 1, `ast.Import` and `ast.ImportFrom` statements are parsed into a file-level symbol table `imports_map`.
- **Aliases:** `from .subpkg.utils import compute_val as alias_compute` creates an entry `{ "mod": "subpkg.utils", "orig": "compute_val", "type": "relative", "level": 1 }`. When `alias_compute(10)` is invoked in `caller_imports`, the engine maps the alias back to `compute_val`, queries the module file, and resolves the target URI `func://test_py_repo/src/test_py_repo/subpkg/utils.py#compute_val` under `TIER_B_SCOPED_IMPORT`.
- **Relative Imports:** In `subpkg/utils.py`, `from ..helpers import root_helper` traverses two directory levels up (`level=2`) from `src/test_py_repo/subpkg/` to locate `src/test_py_repo/helpers.py`, correctly emitting a `TIER_B_SCOPED_IMPORT` edge.

### 3.3 Methods, Self Calls, and Unknown Receivers (Scenarios 6 & 10 - Rule 8 Compliance)
> [!IMPORTANT]
> **Rule 8 Compliance: Unknown Receivers Are Never Converted to Exact Calls.**
> In legacy heuristic graphs, calling `obj.internal_action()` when `obj` is an unannotated function parameter frequently triggered global name matching, erroneously linking to `Service.internal_action()`.

In `test_python_lfcg.py`:
- `self.internal_action()` inside class `Service` resolves via `self.class_stack` to `func://test_py_repo/src/test_py_repo/main.py#Service.internal_action` under `TIER_C_RECEIVER_BOUND`.
- `external_obj.internal_action()` has qualifier `external_obj`. The engine inspects local variable bindings and class definitions, determines that `external_obj`'s type is unbound/unknown, and routes it to `unknown_receiver_unresolved`. It records candidate count $A(e) \ge 1$ for diagnostic logging, but sets `is_resolved=False` and emits **zero edges**.

### 3.4 Shadowing and Local Variable Protection (Scenario 5)
In `caller_shadowing()`:
```python
def caller_shadowing():
    helper_target = lambda: 99
    return helper_target()
```
The AST visitor records assignments (`ast.Assign`, `ast.AnnAssign`, `ast.NamedExpr`) in `self.scope_local_vars`. When `helper_target()` is called, the resolver detects that `helper_target` exists in the local variables of the active function scope. It terminates resolution with `resolution_method="shadowed_by_local_scope"` and emits zero edges, avoiding a false-positive edge to the module-level function `helper_target`.

### 3.5 Dynamic Dispatch, Builtins, and External Libraries (Scenarios 9, 11, 12)
- **Dynamic Dispatch:** Expressions such as `getattr(handler, "dynamic_fn")()` or `locals()()` have non-Name/Attribute AST function nodes. The extraction engine flags `is_dynamic=True` with identifier `<dynamic_call>`, routing to `TIER_E_UNRESOLVED`.
- **Builtins:** Python builtins (`len`, `print`, `range`, `dict`, etc.) are checked against `sys.builtin_module_names` and standard builtins. Calling `len([1, 2, 3])` terminates with `builtin_filter` / `UNRESOLVED`.
- **External Libraries:** `math.sqrt(25)` and `my_path.join("a", "b")` reference external module imports. The engine checks if the module exists within the indexed repository files. Because `math` and `os.path` are not part of the repository codebase, they are resolved as external standard library calls and dropped from edge emission.

### 3.6 Robustness Against Syntax Errors (Scenario 13)
In `syntax_error.py`, malformed Python syntax is supplied.
- Pass 1 catches `SyntaxError` inside `parse_source()`.
- The engine marks `self.file_metadata[file_uri] = {"syntax_error": True}` and safely returns.
- Pass 2 skips AST traversal for syntax-errored files.
- Result: 0 functions registered, 0 edges emitted, 0 unhandled exceptions, zero process crashes.

### 3.7 Determinism and Edge Schema (Scenario 14)
- **Edge Schema Enforcement:** Verified that only `CONTAINS` (File $\to$ Function) and `CALLS` (Function $\to$ Function) edges are emitted. No speculative inheritance, dynamic interface, or class-hierarchy edges exist.
- **Serialization Determinism:** `get_serialized_sha256()` was invoked across multiple independent runs on the test repository. The generated SHA-256 digests were bit-for-bit identical, verifying canonical JSON ordering (sorted keys, deterministic indentation, consistent float formatting).

---

## 4. Full Regression Suite Validation

Following prototype test execution, the full RepoNeedle regression suite was executed across all production and research verification tests:

```bash
pytest tests/
```

**Results:**
- **Collected:** 249 items
- **Passed:** 249 passed in 5.73s
- **Failed:** 0
- **Errors:** 0
- **Regression Invariants Preserved:**
  - `tests/test_ablation_switches.py` (5/5 passed)
  - `tests/test_arm101_production_parity.py` (4/4 passed)
  - `tests/test_graph.py` (8/8 passed)
  - `tests/test_stage3_6_forensic_reconciliation.py` (6/6 passed)
  - `tests/test_stage3_7_component_isolation.py` (8/8 passed)
  - `tests/test_stage3_8_query_conditioned_graph.py` (5/5 passed)
  - `tests/test_stage3_8_reproducibility.py` (8/8 passed)
  - `tests/test_stage3_9_cascade.py` (9/9 passed)
  - `tests/test_stage3_21_production_quality.py` (6/6 passed)

The isolated prototype and test files in `research/stage3_9/prototypes/` introduce zero side effects or regressions to existing RepoNeedle core engines.

---

## 5. Conclusion & Test Acceptance Gate

The Python LFCG prototype satisfies all criteria defined under Phase D:
1. **Pass Rate:** 100% (14/14 unit tests, 249/249 regression tests).
2. **Fail-Closed Behavior:** Verified for shadowing, dynamic dispatch, unknown receivers, builtins, and external modules.
3. **Resilience:** Graceful handling of syntax errors without crashing.
4. **Deterministic Output:** Canonical serialization verified with matching SHA-256 hashes.

The implementation is verified ready for Stage 3.9.3 runtime evaluation and pilot consideration.

