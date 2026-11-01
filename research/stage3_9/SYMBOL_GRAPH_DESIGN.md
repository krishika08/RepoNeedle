# Stage 3.9.1: Refined Symbol Graph Schema & Ambiguity Resolution
## Formal Bi-Level Schema, Typed Invocations, Dynamic Construct Semantics & Deterministic Serialization

**Document ID**: `STAGE3-9-DESIGN-002`  
**Stage**: Stage 3.9.1 — Architecture Design Refinement and Research Governance  
**Date**: November 1, 2026  
**Workspace**: `F:\RepoNeedle`  
**Active Branch**: `research/stage3_8`  
**Development Baseline Reference**: `EXP-386` (Edge-Type-Aware Directional Gating: MRR **0.2062**, Recall@20 **0.5566**, Hit@20 **0.6464**, BCY@8k **0.0556**)  
**Governing Rule**: Do not invent exact relationships when resolution is ambiguous. Explicitly represent uncertainty, target ambiguity, and resolution provenance. All graph structures must be strictly deterministic and serializable.

---

## 1. Node Schema & Deterministic Identity

The bi-level heterogeneous graph $\mathcal{G} = (\mathcal{V}, \mathcal{E})$ defines strict URI schemes for node identity to guarantee repository-wide uniqueness and deterministic ordering:

### 1.1 Node URI Schemes

| Node Type ($\tau_v$) | Deterministic URI Scheme | Concrete Example |
|---|---|---|
| **`FileNode`** | `file://<file_path>` | `file://src/click/core.py` |
| **`ClassNode`** | `class://<file_path>::<class_name>` | `class://src/click/core.py::Command` |
| **`FunctionNode`** | `func://<file_path>::[<parent_scope>::]<func_name>` | `func://src/click/core.py::Command::invoke` |
| **`ExternalSymbolNode`** | `ext://<package_name>::<symbol_name>` | `ext://pytest::fixture` |

### 1.2 Node Attributes Specification

```python
@dataclass(frozen=True)
class FileNode:
    id: str  # "file://src/click/core.py"
    path: str  # "src/click/core.py"
    language: str  # "python", "rust", "go", etc.
    is_test: bool
    is_manifest: bool
    raw_char_len: int
    doc_filter_penalty: float  # 0.5 for non-code, 1.0 for code


@dataclass(frozen=True)
class ClassNode:
    id: str  # "class://src/click/core.py::Command"
    name: str  # "Command"
    file_path: str  # "src/click/core.py"
    start_line: int
    end_line: int
    base_classes: Tuple[str, ...]  # ("BaseCommand",)
    is_interface: bool  # True for Go/Java/TS interfaces and Rust traits
    is_exported: bool


@dataclass(frozen=True)
class FunctionNode:
    id: str  # "func://src/click/core.py::Command::invoke"
    name: str  # "invoke"
    parent_scope: Optional[str]  # "Command" or outer function name
    file_path: str  # "src/click/core.py"
    start_line: int
    end_line: int
    is_method: bool
    is_test: bool
    is_async: bool
    arg_names: Tuple[str, ...]
    decorators: Tuple[str, ...]  # ("@property",)
    overload_count: int  # Number of merged overloaded signatures (Java/TS)
```

---

## 2. Refined Typed Edge Schema & Weight Semantics

Every directed edge $e = (u, v) \in \mathcal{E}$ models a directional semantic dependency with explicit provenance, target ambiguity, and confidence scoring.

### 2.1 Edge Types Specification

| Edge Type ($\tau_e$) | Source ($u$) | Target ($v$) | Directional Meaning | Baseline Multiplier ($\mu$) |
|---|---|---|---|:---:|
| **`CONTAINS`** | `FileNode` | `ClassNode` / `FunctionNode` | File contains the defined symbol. | 1.00 |
| **`DECLARES`** | `ClassNode` | `FunctionNode` | Class declares or implements the method. | 1.00 |
| **`CALLS`** | `FunctionNode` | `FunctionNode` | Function $u$ invokes function/method $v$. | 1.00 (Implementation query)<br>0.15 (Test caller for code query)<br>1.25 (Test caller for test query) |
| **`INHERITS`** | `ClassNode` | `ClassNode` | Subclass $u$ inherits from base class $v$. | 0.85 |
| **`IMPLEMENTS`** | `ClassNode` | `ClassNode` (Interface) | Class/struct $u$ implements interface/trait $v$. | 0.85 |
| **`IMPORTS`** | `FileNode` | `FileNode` / `ClassNode` / `FunctionNode` | File $u$ imports module, class, or function $v$. | 1.00 (0.05 for manifests) |

### 2.2 Mathematical Formulation of Edge Weight
The effective retrieval diffusion weight $w(e)$ for an invocation edge $e = (u, v)$ is calculated as:
$$w(e) = \phi(e) \cdot \frac{1}{\sqrt{A(e)}} \cdot \mu_{\text{intent}}(e) \cdot \psi_{\text{sIDF}}(v)$$

where:
1. **$\phi(e) \in [0.0, 1.0]$** is the resolution provenance confidence score.
2. **$A(e) \ge 1$** is the **Target Ambiguity Factor**, defined as the number of distinct candidate functions in the repository matching the callee identifier. For an exact unique resolution, $A(e) = 1$. For dynamic dispatch matching 4 candidate classes, $A(e) = 4$.
3. **$\mu_{\text{intent}}(e)$** is the query-intent directional gating multiplier (0.15x for test callers on code queries, 1.25x on test queries, 0.05x on manifests).
4. **$\psi_{\text{sIDF}}(v)$** is the callee symbol hub attenuation penalty.

---

## 3. Handling Complex Language & Dynamic Constructs

To prevent ad-hoc heuristics and hallucinated graph linkages, RepoNeedle establishes strict, deterministic handling rules for complex programming constructs:

### 3.1 Overloaded Methods (Java, TypeScript)
- In Java and TypeScript, multiple methods in the same class may share the identical name with different formal parameters (e.g. `execute(Context)` vs `execute(Context, Options)`).
- **Handling Rule**: Overloaded methods within the same class/file are **merged into a single canonical `FunctionNode`**.
  - `start_line` is the start line of the first overload; `end_line` is the end line of the last overload.
  - `overload_count` records the total number of variants ($N_{\text{overloads}}$).
  - Outgoing and incoming calls from all variants are unioned into the canonical node.

### 3.2 Aliases and Re-Exports (Python, Rust, JavaScript)
- Python: `from click.core import Command as Cmd`
- Rust: `pub use crate::parser::Command;`
- JavaScript: `export { default as Command } from './core';`
- **Handling Rule**: Aliases do not create phantom symbol nodes. Instead, the parser maintains an internal **Symbol Alias Map**:
  $$\text{AliasMap}[(caller\_file, \text{alias\_name})] = \text{canonical\_symbol\_id}$$
  Call sites invoking the alias name are resolved directly to the underlying canonical symbol definition with an `AST_IMPORT_BOUND` provenance score ($\phi = 0.95$).

### 3.3 Inheritance and Trait Hierarchies
- When class $B$ subclasses class $A$ (`class MultiCommand(Command)`), an explicit directed edge is created: `class://B` $\to$ `class://A` (`INHERITS`).
- **Method Resolution Traversal**:
  If function $f$ invokes `cmd.format_usage()` where `cmd` is known to be `MultiCommand`, but `MultiCommand` does not define `format_usage`:
  - Traverse incoming `INHERITS` edges: `MultiCommand` $\to$ `Command`.
  - If `Command` defines `format_usage`, create invocation edge `f` $\to$ `Command::format_usage` with `INHERITED_CLASS_METHOD` provenance ($\phi = 0.75$).

### 3.4 Dynamic Dispatch & Duck Typing
- In dynamic languages, `handler.process(event)` cannot identify the concrete class of `handler` statically.
- **Handling Rule**:
  1. If `process` is a globally unique method name across all classes in the repository, create edge with `STRUCTURAL_UNIQUE_METHOD` provenance ($\phi = 0.50$, $A(e) = 1$).
  2. If `process` is defined across $2 \le N \le 3$ classes, create fractional edges to all candidate methods with ambiguity dampening: $w(e) = \phi \cdot \frac{1}{\sqrt{N}}$ ($\phi = 0.40$).
  3. If $N > 3$, **suppress the call entirely ($\phi = 0.0$)**. Do not invent arbitrary edges that create artificial hubs.

### 3.5 Decorators and Attributes (Python, Rust, Java)
- Python `@property`: Flagged as an attribute getter. Attribute accesses (`obj.name`) do not form invocation edges unless the property name is non-generic and globally unique.
- Python `@classmethod` / `@staticmethod`: Handled identically to standard methods, stripping the implicit `cls` or `self` parameter from formal argument lists.
- Java annotations (`@Test`, `@Override`): Stored in `FunctionNode.decorators`. In particular, `@Test` explicitly sets `is_test = True`.

### 3.6 Nested Functions and Closures
- Inner helper functions defined within an enclosing function (e.g. `def helper(): ...` inside `def main(): ...`):
  - Assigned qualified ID: `func://path::main::helper`.
  - Invocations between `main` and `helper` are classified as `AST_LOCAL_CALL` ($\phi = 1.00$).
  - External callers cannot invoke `helper` directly; outer `main` serves as the public interface node.

### 3.7 Go Interfaces & TypeScript Structural Typing
- Go interfaces (e.g. `type Reader interface { Read(p []byte) (n int, err error) }`):
  - Interface methods are modeled as `FunctionNode` under the interface `ClassNode`.
  - Structs implementing the exact method signatures receive an `IMPLEMENTS` edge to the interface.
  - To prevent combinatorial explosion, structural interface matching is only performed for interfaces with $\ge 2$ methods or unique method names. Single-method generic interfaces (`Stringer`, `Reader`) are treated as external utility contracts.

### 3.8 Unresolved References & Standard Libraries
- Calls to standard library functions (`len`, `print`, `range`, `fmt.Println`, `tokio::spawn`, `System.out.println`) and external packages (`requests.get`, `pytest.fixture`):
  - Routed to `ExternalSymbolNode` (`ext://<pkg>::<name>`).
  - **Graph Invariant**: `ExternalSymbolNode` instances are strictly terminal sinks. They **never propagate diffusion energy** across repository files.

### 3.9 Generated Code and Macros
- Source files containing markers like `@generated`, `DO NOT EDIT`, or minified files (`*.min.js`):
  - Excluded from the fine-grained symbol layer.
  - Retained at the coarse file layer with a downweighted document filter penalty (0.50x).

---

## 4. Deterministic Graph Serialization & Ordering

To ensure bit-for-bit reproducibility across platforms, operating systems, and Python versions:

1. **Deterministic Ordering Contract**:
   - Nodes are sorted lexicographically by their unique URI ID:
     ```python
     sorted_nodes = sorted(graph.nodes(data=True), key=lambda x: x[0])
     ```
   - Edges are sorted lexicographically by the tuple `(source_id, target_id, edge_type)`:
     ```python
     sorted_edges = sorted(graph.edges(data=True), key=lambda x: (x[0], x[1], x[2].get("edge_type", "")))
     ```
2. **Versioned Artifact Format (`v1.0.0`)**:
   - Graph metadata is serialized to `research/stage3_9/SYMBOL_GRAPH_SCHEMA.json`:
     ```json
     {
       "schema_version": "1.0.0",
       "created_at": "2026-11-01T04:00:00Z",
       "node_types": ["FileNode", "ClassNode", "FunctionNode", "ExternalSymbolNode"],
       "edge_types": ["CONTAINS", "DECLARES", "CALLS", "INHERITS", "IMPLEMENTS", "IMPORTS", "TESTS_TARGET"],
       "provenance_tiers": [
         {"tier": "AST_EXACT_QUALIFIED", "confidence": 1.00},
         {"tier": "AST_LOCAL_CALL", "confidence": 1.00},
         {"tier": "AST_IMPORT_BOUND", "confidence": 0.95},
         {"tier": "POLYGLOT_RECEIVER_BOUND", "confidence": 0.90},
         {"tier": "GLOBAL_UNIQUE_SYMBOL", "confidence": 0.80},
         {"tier": "INHERITED_CLASS_METHOD", "confidence": 0.75},
         {"tier": "DIR_LOCAL_HEURISTIC", "confidence": 0.65},
         {"tier": "STRUCTURAL_UNIQUE_METHOD", "confidence": 0.50},
         {"tier": "AMBIGUOUS_POLYGLOT_CALL", "confidence": 0.30}
       ]
     }
     ```
