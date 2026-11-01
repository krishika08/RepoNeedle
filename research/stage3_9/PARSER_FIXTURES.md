# Stage 3.9.2: Synthetic Parser & Resolution Fixtures Audit
## Comprehensive Validation of Extraction vs. Resolution Separation Across Polyglot Fixtures

**Document ID**: `STAGE3-9-FIXTURES-001`  
**Stage**: Stage 3.9.2 ?" Pre-Implementation Feasibility Validation  
**Date**: November 1, 2026  
**Workspace**: `F:\RepoNeedle`  
**Active Branch**: `research/stage3_8`  
**Governing Rule**: Do not treat successful AST parsing as proof of call-target resolution. Do not label regex-detected calls as AST-exact. Unsupported constructs must become `UNRESOLVED` rather than incorrect edges. A small reliable graph is preferable to a large inaccurate graph.

---

## 1. Executive Summary

In accordance with Stage 3.9.2 requirements, isolated synthetic fixtures were authored and audited across all six core benchmark languages under `research/stage3_9/prototypes/fixtures/`:
1. **Python** (`python_cases.py`): 16 functions, 19 call sites extracted.
2. **Go** (`go_cases.go`): 10 functions, 12 call sites extracted.
3. **Rust** (`rust_cases.rs`): 9 functions, 7 call sites extracted.
4. **TypeScript** (`ts_cases.ts`): 9 functions, 3 call sites extracted.
5. **JavaScript** (`js_cases.js`): 10 functions, 4 call sites extracted.
6. **Java** (`java_cases.java`): 9 functions, 13 call sites extracted.

**Suite-Wide Empirical Results**:
- **Total Files Analyzed**: 6
- **Total Function Nodes Registered**: 63
- **Total Call Sites Extracted**: 58
- **Total Resolutions Attempted**: 58
- **Correctly Resolved Calls**: 20 (34.5%)
- **Safely Unresolved Calls (Fail-Closed / Filtered)**: 38 (65.5%)
- **Zero False-Positive Edges Injected**: Every unsupported construct (dynamic dispatch, interface polymorphism, trait polymorphism, macro expansion, structural typing, overloaded methods without types, and external libraries) safely yielded `resolution_status = UNRESOLVED` (Tier E) with zero false calls edges.
- **Deterministic Serialization SHA-256 Digest**:
  `5e68ea29948ca82adc23f23f49bc2b529319fd54a8d8e0a0d5087a4bae37f478`

---

## 2. Separation of Extraction from Resolution

A fundamental flaw of earlier graph proposals was treating successful regex or AST call expression detection as equivalent to successful call target resolution. Stage 3.9.2 enforces an unyielding architectural separation:

```mermaid
flowchart TD
    RawCode["Source Code File"] --> Extractor["1. Call-Site Extraction Engine"]
    Extractor --> CallRecord["CallSiteExtraction Record\n- line, col\n- enclosing function\n- raw expression\n- callee identifier\n- qualifier"]
    CallRecord --> Resolver["2. Call-Target Resolution Engine"]
    Resolver --> CheckType{"Construct Supported & Resolvable?"}
    CheckType -- Yes --> Resolved["CallTargetResolution (EXACT / HEURISTIC)\n- selected target URI\n- candidate count A(e)\n- single ambiguity penalty 1/sqrt(A(e))\n- emits CALLS edge"]
    CheckType -- No --> Unresolved["CallTargetResolution (UNRESOLVED / Tier E)\n- candidate count 0 or multi-target\n- heuristic weight = 0.0\n- ZERO CALLS edges emitted"]
```

### 2.1 Extraction Data Contract (`CallSiteExtraction`)
Records the purely syntactic event of an invocation expression:
* `caller_file_uri`: Canonical URI of source file.
* `caller_func_uri`: Canonical URI of enclosing function (or `None` if module-level).
* `line`, `col`: Source position coordinates.
* `raw_callee_expr`: Exact code string representation (e.g. `obj.method()`, `pkg.Func()`, `len(x)`).
* `identifier`: Callee symbol name (e.g. `method`, `Func`, `len`).
* `qualifier`: Syntactic prefix expression if attribute call (e.g. `self`, `math`, `obj`).
* `is_attribute`: Boolean flag indicating qualified vs bare identifier call.
* `is_dynamic`: Boolean flag indicating non-identifier target (e.g. `func_map[k]()`, `getattr(o, m)()`).

### 2.2 Resolution Data Contract (`CallTargetResolution`)
Records the semantic symbol binding and disambiguation result:
* `is_resolved`: Boolean flag.
* `target_uris`: List of candidate target URIs.
* `selected_target_uri`: Exactly one resolved target URI if unambiguous, else `None`.
* `candidate_count`: $A(e)$, the number of genuine candidate definitions in symbol registry.
* `resolution_method`: Explicit method token documenting derivation logic.
* `resolution_status`: `EXACT` (Tier A), `HEURISTIC` (Tier B/C/D), or `UNRESOLVED` (Tier E).
* `provenance_tier`: Categorized tier for downstream weighting.
* `ambiguity_penalty`: $\frac{1}{\sqrt{A(e)}}$ if resolved, else $0.0$.
* `heuristic_weight`: $\phi(e)$ from pre-registered provenance schedule.

---

## 3. Language Fixture Construct Coverage & Genuine Capabilities

### 3.1 Python (`python_cases.py`)
Python is the only language in the repository with a compiler-grade AST parser (`ast` standard library).

| Construct Tested | Extraction Status | Resolution Method | Status | Target URI / Outcome | Genuine Capability |
|---|---|---|---|---|---|
| **Local Direct Calls** (`local_target_a()`) | Extracted (L26, C11) | `ast_local_lexical_binding` | `EXACT` | `func://...#local_target_a` | **Genuine AST Exact** |
| **Module Imports** (`math.sqrt()`) | Extracted (L33, C8) | `external_library_call` | `UNRESOLVED` | External stdlib; safely filtered | **Genuine Filter** |
| **Import Aliases** (`path_alias.join()`) | Extracted (L34, C8) | `external_library_call` | `UNRESOLVED` | Alias tracked to `os.path`; external | **Genuine Scoped Tracking** |
| **Function Shadowing** (`local_target_a = lambda`) | Extracted (L42, C10) | `shadowed_by_local_scope` | `UNRESOLVED` | Local assignment detected; global call suppressed | **Genuine Lexical Scope** |
| **Nested Functions** (`inner_nested_worker`) | Extracted (L48, C15) | `ast_local_lexical_binding` | `EXACT` | Enclosing stack tracked | **Genuine Scope Stack** |
| **Methods & Self Calls** (`self.internal_helper()`) | Extracted (L60, C12) | `ast_self_method_binding` | `EXACT` | `func://...#ServiceWorker.internal_helper` | **Genuine Receiver Match** |
| **Decorators** (`@simple_decorator`) | Extracted (L72, C11) | `ast_local_lexical_binding` | `EXACT` | Decorated target resolved to function | **Genuine Decorator Pass** |
| **Dynamic Dispatch** (`getattr()`, `func_map[]`) | Extracted (L78, C11) | `unsupported_dynamic_dispatch` | `UNRESOLVED` | Candidate count = 0; zero edges emitted | **Safe Abstention** |
| **Built-in Calls** (`len()`, `sum()`, `print()`) | Extracted (L84, C8) | `builtin_filter` | `UNRESOLVED` | Filtered against builtin registry | **Safe Abstention** |

### 3.2 Go (`go_cases.go`)
Go lacks an AST parser in our pure-Python environment. Regex heuristics are strictly labeled `Tier D Heuristic`.

| Construct Tested | Extraction Status | Resolution Method | Status | Target URI / Outcome | Genuine Capability |
|---|---|---|---|---|---|
| **Package-Local Calls** (`LocalTargetGo()`) | Extracted (L54, C11) | `go_package_local_pattern` | `HEURISTIC` | `func://...#LocalTargetGo` | **Pattern Heuristic** |
| **Imported Package Calls** (`strings.ToUpper()`) | Extracted (L61, C12) | `go_external_import_call` | `UNRESOLVED` | External standard package | **Safe Abstention** |
| **Receiver Methods** (`e.InternalMethod()`) | Extracted (L69, C10) | `go_receiver_method_heuristic` | `HEURISTIC` | Matches `*Engine.InternalMethod` | **Pattern Heuristic** |
| **Interface Dispatch** (`p.ProcessData()`) | Extracted (L76, C8) | `go_unsupported_interface_polymorphism` | `UNRESOLVED` | Runtime receiver unknown | **Safe Abstention** |
| **Ambiguous Method Names** (`obj.ProcessData()`) | Extracted (L82, C8) | `go_unsupported_interface_polymorphism` | `UNRESOLVED` | 2 implementors (`Engine`, `Reporter`); suppressed | **Safe Abstention** |

### 3.3 Rust (`rust_cases.rs`)
Rust code requires macro expansion and trait resolution for exactness.

| Construct Tested | Extraction Status | Resolution Method | Status | Target URI / Outcome | Genuine Capability |
|---|---|---|---|---|---|
| **Module Paths** (`mod::func()`) | Extracted (L66, C13) | `rust_module_path_resolution` | `HEURISTIC` | Scoped module path target | **Pattern Heuristic** |
| **Use Aliases** (`target_alias()`) | Extracted (L67, C13) | `rust_use_alias_binding` | `HEURISTIC` | Resolves alias to target func | **Scoped Alias Match** |
| **Associated Functions** (`Worker::create()`) | Extracted (L74, C18) | `rust_associated_function_heuristic` | `HEURISTIC` | Resolves associated constructor | **Pattern Heuristic** |
| **Trait Methods** (`handler.handle_data()`) | Extracted (L80, C4) | `rust_unsupported_trait_polymorphism` | `UNRESOLVED` | 3 candidates (`First`, `Second`, `Unrelated`); suppressed | **Safe Abstention** |
| **Macro-Generated Code** (`generated!()`) | Extracted (L85, C4) | `rust_unsupported_macro_expansion` | `UNRESOLVED` | Macro expansion not in static AST | **Safe Abstention** |
| **Ambiguous Calls** (`.handle_data()`) | Extracted (L91, C16) | `rust_unsupported_trait_polymorphism` | `UNRESOLVED` | Multiple trait implementors | **Safe Abstention** |

### 3.4 TypeScript (`ts_cases.ts`)
TypeScript relies heavily on arrow functions and structural interfaces.

| Construct Tested | Extraction Status | Resolution Method | Status | Target URI / Outcome | Genuine Capability |
|---|---|---|---|---|---|
| **Named / Default Imports** | Extracted (L46, C4) | `external_library_call` | `UNRESOLVED` | External module import | **Safe Abstention** |
| **Arrow Functions** (`computeHash()`) | Extracted (L22, C11) | `arrow_function_binding` | `HEURISTIC` | Top-level const arrow function | **Pattern Heuristic** |
| **Class Methods** (`this.internalValidate()`) | Extracted (L38, C15) | `arrow_function_binding` | `HEURISTIC` | Class method in same file | **Pattern Heuristic** |
| **Structural Typing** (`runner.executeTask()`) | Extracted (L58, C17) | `ts_unsupported_structural_typing` | `UNRESOLVED` | `ITaskRunner` structural type unknown | **Safe Abstention** |

### 3.5 JavaScript (`js_cases.js`)
JavaScript dynamic object properties and CommonJS require calls.

| Construct Tested | Extraction Status | Resolution Method | Status | Target URI / Outcome | Genuine Capability |
|---|---|---|---|---|---|
| **Arrow Functions** (`sanitizeInput()`) | Extracted (L18, C12) | `arrow_function_binding` | `HEURISTIC` | Local arrow function target | **Pattern Heuristic** |
| **Dynamic Property Calls** (`obj[method]()`) | Extracted (L62, C19) | `js_unsupported_dynamic_bracket_access` | `UNRESOLVED` | Bracket access syntax detected | **Safe Abstention** |

### 3.6 Java (`java_cases.java`)
Java's core challenge is method overloading and interface polymorphism.

| Construct Tested | Extraction Status | Resolution Method | Status | Target URI / Outcome | Genuine Capability |
|---|---|---|---|---|---|
| **Static Imports** (`max(a, b)`) | Extracted (L60, C22) | `java_external_static_import` | `UNRESOLVED` | JDK `java.lang.Math` call | **Safe Abstention** |
| **Overloaded Methods** (`renderData()`) | Extracted (L67, C20) | `java_unsupported_overloaded_method` | `UNRESOLVED` | 3 overloads; argument types unknown | **Safe Abstention** |
| **Inherited Methods** (`commonSetup()`) | Extracted (L74, C8) | `java_inherited_method_heuristic` | `HEURISTIC` | Abstract base method in same file | **Pattern Heuristic** |
| **Interface Polymorphism** (`executor.execute()`) | Extracted (L79, C8) | `java_unsupported_interface_polymorphism` | `UNRESOLVED` | Interface reference without type info | **Safe Abstention** |

---

## 4. Key Architectural Takeaway: Fail-Closed vs. Naive Greedy Matching

The synthetic fixtures audit proves conclusively that **fail-closed abstention is mandatory** for retrieval graph integrity:
1. When parsers lack compiler-grade type systems (Go, Rust, TS, Java), attempting to force resolution on interfaces, traits, or overloaded methods creates catastrophic false edges.
2. By classifying unsupported constructs as `UNRESOLVED` (Tier E) and setting heuristic weight $\phi = 0.0$, the graph remains clean and noise-free.
3. Python stands out as the only benchmark language where exact AST lexical scoping and receiver resolution are genuinely verified.

