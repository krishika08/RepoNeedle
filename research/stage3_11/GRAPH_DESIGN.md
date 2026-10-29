# RepoNeedle Stage 3.11: Function-Level Graph Architecture and Design Specification

**Document**: `research/stage3_11/GRAPH_DESIGN.md`  
**Stage**: Stage 3.11 — Function-Level Graph Retrieval Research  
**Author**: Antigravity Research Agent  
**Date**: October 29, 2026  
**Status**: APPROVED DESIGN SPECIFICATION  

---

## 1. Motivation and Problem Statement

Stage 3.10 introduced `TEST-GRAPH`, establishing a statistically significant improvement ($p = 0.000964$) over `CONTROL-CASCADE`. However, **90.7% of all queries (313 / 345) remained exact ties**. 

Forensic auditing revealed the root cause:
- `TEST-GRAPH` exclusively mapped class and method names in production files to test files exercising them.
- In non-test tasks (`trace2code`, `comment2context`, `edit2ripple`), interacting production files (e.g. caller $\to$ callee, handler $\to$ middleware, route $\to$ controller) had **zero** invocation edges in the graph.
- The repository graph relied solely on coarse, file-level imports (`from foo import bar`). Because Python and polyglot imports frequently target package namespaces (`from . import utils`, `import os`), file-to-file import edges were either missing or degenerated into high-degree star hubs (`__init__.py`).

Stage 3.11 addresses this gap by engineering a fine-grained, language-aware **function-level call graph** that extracts concrete function definitions, call sites, and caller-callee relationships while strictly rejecting false-positive cross-product edges.

---

## 2. Graph Taxonomy: Edge Provenance and Confidence

To prevent graph pollution and preserve lexical relevance, graph edges are partitioned into three explicit tiers:

```
+-------------------------------------------------------------------------+
| Level 1: Verified Direct Call Edges (Confidence 0.90 - 1.00)            |
| - Explicitly imported function calls: from utils import helper; helper()|
| - Module-qualified calls: import utils; utils.helper()                  |
| - Intra-file function/method calls: self.method() or local_fn()         |
| - Globally unique repository functions: exactly one definition in repo   |
| - Direct class constructions in tests (Stage 3.10 linkage)              |
+-------------------------------------------------------------------------+
                                   |
+-------------------------------------------------------------------------+
| Level 2: Structural Dependency Edges (Confidence 0.65 - 0.85)           |
| - Unique class method dispatch: obj.method() where method is unique     |
| - Package/Directory-local calls: resolved within same directory         |
| - Polyglot package-scoped calls: pkg.Func() in Go, crate::fn() in Rust  |
+-------------------------------------------------------------------------+
                                   |
+-------------------------------------------------------------------------+
| Level 3: Rejected / Filtered Ambiguities (Do Not Link)                  |
| - Builtins and standard library functions (len, print, range, open)     |
| - Generic method names (get, set, run, exec, call, read, write, close)  |
| - Ambiguous functions with >3 definitions and no qualifying import      |
| - Dynamic dispatch / eval / getattr expressions                         |
+-------------------------------------------------------------------------+
```

---

## 3. Polyglot Extraction Mechanics

### 3.1 Python (AST Primary, Fallback Token Regex)
1. **Definitions**:
   - `ast.FunctionDef`, `ast.AsyncFunctionDef`:
     - Scope: Recorded as module-level function if parent is `Module`, or method if parent is `ClassDef`.
     - Parameters, decorators (`@property`, `@staticmethod`, `@classmethod`, `@pytest.fixture`), and line ranges.
   - `ast.ClassDef`:
     - Class name, bases, and catalog of contained methods.
2. **Call Sites**:
   - `ast.Call`:
     - `ast.Name(id='fn')`: Direct call. Checked against active imports (`ImportFrom`, `Import`) and file-local definitions. If not imported, resolved against repository-wide unique symbols.
     - `ast.Attribute(value=ast.Name(id='mod'), attr='fn')`: Module attribute call. If `mod` matches an imported module, unambiguously links caller to target module file.
     - `ast.Attribute(value=..., attr='method')`: Class method invocation. Resolved against class method registry.
3. **Module Resolution**:
   - Normalize module paths: `src/click/core.py` $\to$ `click.core`.
   - Resolve relative imports (`from .utils import make_str`).

### 3.2 Go
1. **Definitions**:
   - `func FuncName(...)`: Package-level function.
   - `func (r *Receiver) MethodName(...)`: Method tied to receiver type.
2. **Call Sites**:
   - `pkg.FuncName(...)`: Matches package import or directory sibling.
   - `recv.MethodName(...)`: Method invocation.

### 3.3 Rust
1. **Definitions**:
   - `fn func_name(...)`: Function.
   - `impl Type { fn method_name(...) }`: Type method.
2. **Call Sites**:
   - `path::func(...)`: Crate/module function call.
   - `val.method(...)`: Method call.

### 3.4 TypeScript / JavaScript
1. **Definitions**:
   - `function funcName(...)`, `const funcName = (...) => ...`, class methods.
2. **Call Sites**:
   - Named imports `import { fn } from './target'`.
   - Direct call `fn(...)`.

---

## 4. Propagation and Score Diffusion Mechanics

### 4.1 Directional Asymmetry
In code retrieval, caller $\to$ callee and callee $\to$ caller relationships convey different information:
- **Forward Propagation (Caller $\to$ Callee)**: If file $A$ is a lexical seed and calls function in file $B$, file $B$ provides implementation details.
  $$\text{Boost}(B) = \text{Score}(A) \times W_{\text{forward}} \times \text{conf} \times \frac{1}{\sqrt{\text{deg}_{\text{out}}(A) \cdot \text{deg}_{\text{in}}(B)}}$$
  where $W_{\text{forward}} = 0.25$.
- **Reverse Propagation (Callee $\to$ Caller)**: If file $B$ is a lexical seed and is called by file $A$, file $A$ provides context or integration usage.
  $$\text{Boost}(A) = \text{Score}(B) \times W_{\text{reverse}} \times \text{conf} \times \frac{1}{\sqrt{\text{deg}_{\text{in}}(B) \cdot \text{deg}_{\text{out}}(A)}}$$
  where $W_{\text{reverse}} = 0.20$.

### 4.2 Degree Normalization
Nodes with excessive fan-out (e.g. utility files imported everywhere) would otherwise dominate retrieval. Degree normalization scales the diffusion weight inversely with the geometric mean of seed out-degree and target in-degree.

### 4.3 Package Boundary Fencing
Graph diffusion is fenced within package / crate boundaries:
- Two files may propagate graph score if:
  1. They reside in the same directory, or
  2. One directory is a subdirectory of the other, or
  3. They belong to the same crate / Go package / npm workspace member, or
  4. An explicit inter-crate path dependency is declared in `Cargo.toml` / `go.mod` / `package.json`.

Spurious edges crossing unrelated top-level subsystems are discarded.

---

## 5. Experimental Variants

1. **`BASE-BM25`**: Length-normalized Okapi BM25 baseline.
2. **`CONTROL-CASCADE`**: Rank 1–3 lexical freeze, file-level imports, package fencing.
3. **`TEST-GRAPH`**: `CONTROL-CASCADE` + Stage 3.10 class-to-test invocations.
4. **`DEGREE-CONTROL`**: `CONTROL-CASCADE` + degree-matched random invocation graph.
5. **`BASE-REPOMAP`**: Pinned official RepoMap (commit `9e4d689`).
6. **`FUNCTION-GRAPH`**: Full function-level graph (Level 1 verified + Level 2 structural) with Rank 1–3 freeze.
7. **`FUNCTION-GRAPH-VERIFIED`**: Function-level graph strictly restricted to Level 1 verified call edges.
8. **`FUNCTION-GRAPH-ABLATION`**: Function-level graph without Level 2 structural edges.
9. **`FUNCTION-GRAPH-NO-FREEZE`**: Full function-level graph with Rank 1–3 freeze removed (evaluating lexical freeze safety).

---

## 6. Diagnostic Metrics

The following metrics are collected per repository snapshot:
- `num_functions`: Total declared functions/methods.
- `num_call_sites`: Total extracted call sites.
- `num_verified_edges`: Level 1 verified edges.
- `num_structural_edges`: Level 2 structural edges.
- `num_unresolved_calls`: Calls unable to be linked.
- `num_ambiguous_calls`: Calls matching $>3$ candidates without qualifying import.
- `graph_construction_time_ms`: Wall-clock indexing duration.
- `memory_rss_mb`: Native process resident set size.

