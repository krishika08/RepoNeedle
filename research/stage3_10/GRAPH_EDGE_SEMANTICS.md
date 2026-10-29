# RepoNeedle Stage 3.10 — Graph Edge Semantics and Disambiguation Specification

## 1. Scope & Objective

This document defines the static analysis rules, evidence hierarchy, hub suppression algorithms, and score propagation mechanics used to construct the class-to-test invocation graph in RepoNeedle Stage 3.10.

## 2. Evidence Hierarchy & Priority

Static analysis inherently encounters ambiguity when multiple production files declare identical class or method names, or when imports are wildcarded. To preserve high precision, RepoNeedle establishes a strict 4-level evidence priority:

```
Level 4: DIRECT_CLASS_CONSTRUCTION  (Confidence: 0.95)
Level 3: DIRECT_METHOD_CALL         (Confidence: 0.85)
Level 2: IMPORTED_MODULE_CALL       (Confidence: 0.80)
Level 1: CLASS_IMPORT               (Confidence: 0.65)
```

If multiple evidence types link a test file to a production file, the edge retains the highest-confidence evidence label and score.

### Evidence Definitions
1. **`DIRECT_CLASS_CONSTRUCTION` (0.95)**:
   - Python: AST `Call` where `node.func` is `ast.Name(id=ClassName)`.
   - Rust: `ClassName::new(...)`, `ClassName::default()`, `ClassName::from(...)`, or struct instantiation `ClassName { ... }`.
   - Go: `&ClassName{...}`, `NewClassName(...)`, or `MakeClassName(...)`.
   - TypeScript/JavaScript: `new ClassName(...)`.

2. **`DIRECT_METHOD_CALL` (0.85)**:
   - AST `Call` where `node.func` is `ast.Attribute(attr=method_name)` and `method_name` uniquely resolves to a single production class across the repository.
   - Go receiver method calls: `t.MethodName(...)`.

3. **`IMPORTED_MODULE_CALL` (0.80)**:
   - AST `Call` where `node.func` is `module.ClassName(...)`.
   - Resolved by checking the test file's imported module paths against the production file's package path.

4. **`CLASS_IMPORT` (0.65)**:
   - AST `ImportFrom` importing `ClassName` directly: `from mymodule import MyClass`.
   - Rust: `use crate::path::ClassName;`.

## 3. Disambiguation and Hub Suppression Algorithms

Uncontrolled static linking creates catastrophic high-degree hubs. For instance, classes named `Config`, `Context`, `Options`, or `Client` exist in almost every large repository. Linking every test referencing `Config` to every file defining a `Config` class destroys retrieval selectivity.

### A. Generic Symbol Blacklist
Symbols belonging to the canonical generic set are suppressed unless qualified by an explicit import:
```python
GENERIC_NAMES = {
    "Config", "Options", "State", "Context", "Base", "Error", "Item",
    "Entry", "Node", "Handler", "Client", "Response", "Request",
    "Builder", "Helper", "Result", "Event", "Manager", "Data",
    "Value", "Info", "Model", "Service", "Session", "Task", "App",
    "Engine", "Parser", "Server", "Type", "Param", "Params"
}
```
If a class name is in `GENERIC_NAMES`, an edge is created **only** if the test file contains an explicit import statement matching the production file path. Otherwise, an unresolved diagnostic entry is logged:
`AMBIGUOUS_GENERIC_CLASS_WITHOUT_QUALIFYING_IMPORT`.

### B. High-Frequency Multi-File Threshold
If a non-generic class name is defined in $> 3$ distinct production files:
1. Directory Proximity Check: If exactly one defining production file shares the same directory or immediate parent with the test file, that file is selected ($\text{conf} = 0.80$).
2. Import Path Check: If exactly one defining production file matches an import string in `test_doc.imports`, that file is selected ($\text{conf} = 0.80$).
3. Fail-Closed Disambiguation: If neither check produces a unique target, no edge is created, and the reference is logged as `MULTI_FILE_DEFINITION_UNRESOLVED`.

## 4. Score Propagation Mechanics

Relevance is propagated bidirectionally between top-3 lexical seed files and candidate files for ranks $\ge 4$:

### A. Production Seed to Test File
When a production file $p$ is in the top-3 lexical seeds with BM25 score $S_p$:
For each test file $t \in \text{ProdToTests}(p)$:
$$\text{Boost}_t = S_p \cdot w_{\text{class\_to\_test}} \cdot \frac{1}{\sqrt{\text{deg}_{\text{out}}(p) \cdot \text{deg}_{\text{in}}(t)}}$$
where $w_{\text{class\_to\_test}} = 0.35$.

### B. Test Seed to Production File
When a test file $t$ is in the top-3 lexical seeds with BM25 score $S_t$:
For each production file $p \in \text{TestToProds}(t)$:
$$\text{Boost}_p = S_t \cdot w_{\text{class\_to\_test}} \cdot \frac{1}{\sqrt{\text{deg}_{\text{out}}(t) \cdot \text{deg}_{\text{in}}(p)}}$$

### C. Degree Normalization
The symmetric factor $\frac{1}{\sqrt{\text{deg}_{\text{out}} \cdot \text{deg}_{\text{in}}}}$ guarantees that:
- Tests that instantiate dozens of classes do not flood all production files.
- Production classes instantiated by hundreds of tests do not artificially promote every single test.

## 5. Degree-Matched Bipartite Control Graph (Arm C)

To rigorously test whether gains arise from genuine semantic invocation relationships rather than mere graph density:
1. For each snapshot, the set of test nodes $V_{\text{test}}$ and production nodes $V_{\text{prod}}$ with invocation edges is identified.
2. A random bipartite graph is constructed using a deterministic pseudo-random generator (seed 42):
   - For each production file $p$, exactly $\text{deg}(p)$ test files are sampled uniformly without replacement from $V_{\text{test}}$.
   - For each test file $t$, exactly $\text{deg}(t)$ production files are sampled uniformly without replacement from $V_{\text{prod}}$.
3. Arm C propagates relevance across this degree-matched random graph using identical weights and normalization.
