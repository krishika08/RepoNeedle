# Tree-sitter Structural Extraction (optional)

**Status**: opt-in, on `main`, **not in a published release yet** (RepoNeedle 1.2.0 on PyPI does not include it).
**Scope**: the function-level call graph (`FunctionGraphEngine`) used by the opt-in `arm101` ranker.
**Validation report**: [reports/v2_completion/tree_sitter/REPORT.md](../reports/v2_completion/tree_sitter/REPORT.md)

This is **syntax-aware extraction, not semantic code intelligence**. Tree-sitter gives RepoNeedle an accurate syntax tree: real function and method boundaries, line numbers, import declarations and call expressions, with comments and strings excluded. It does **not** infer types, resolve overloads, expand macros, follow build systems or know which object a method is called on. Relationships that syntax alone cannot establish are left to the existing heuristic resolver, with its existing confidence values, or produce no edge at all.

---

## 1. What changes, and what does not

| Area | With `structural_parser="tree_sitter"` | Default (`"regex"`) |
| :--- | :--- | :--- |
| TypeScript/TSX, Go, Rust, Java, C++ function-graph extraction | Tree-sitter syntax trees | Regular expressions (1.2.0 behaviour) |
| Python | `ast` extractor (unchanged) | `ast` extractor |
| JavaScript (`.js`, `.jsx`, `.mjs`, `.cjs`), C (`.c`), other files | Regex extractor (unchanged) | Regex extractor |
| Import-bound call resolution | New, stricter step (§4) | — |
| Ranking weights, fusion, routing, CUD-Pack packing and focus spans, abstention | Unchanged | Unchanged |
| Repository graph (`RepoGraph`: PageRank, test/ripple linkage used by `legacy`) | Unchanged | Unchanged |
| Rankers affected | `arm101` only (the only consumer of the function graph) | — |
| MCP tools and CLI | Unchanged; there is no CLI or MCP switch | — |

Because only `arm101` reads the function graph, enabling Tree-sitter does not change results of the default `legacy` ranker or of `bm25`, `cascade` and `change_impact`.

## 2. Installation

The `treesitter` extra is defined on `main` and is not in the published 1.2.0 package. Install from a source checkout:

```bash
git clone https://github.com/krishika08/RepoNeedle.git
cd RepoNeedle
pip install -e ".[treesitter]"
```

This installs prebuilt wheels only (no compiler needed), for Python 3.10–3.12 on Windows, Linux and macOS:

| Package | Version range | Tested | Grammar ABI |
| :--- | :--- | :--- | :--- |
| `tree-sitter` (runtime) | `>=0.25.2,<0.27` | 0.25.2, 0.26.1 | loads ABI 13–15 |
| `tree-sitter-typescript` (TypeScript + TSX) | `>=0.23.2,<0.24` | 0.23.2 | 14 |
| `tree-sitter-go` | `>=0.25.0,<0.26` | 0.25.0 | 15 |
| `tree-sitter-rust` | `>=0.24.2,<0.25` | 0.24.2 | 15 |
| `tree-sitter-java` | `>=0.23.5,<0.24` | 0.23.5 | 14 |
| `tree-sitter-cpp` | `>=0.23.4,<0.24` | 0.23.4 | 14 |

- **Why the runtime floor is 0.25.** The Go and Rust grammars are ABI 15. Runtimes 0.23 and 0.24 reject them with `Incompatible Language version 15`.
- **Why the grammars' `[core]` extras are not used.** Those extras allow runtimes as old as 0.22 (`tree-sitter-rust[core]`) or 0.24 (`tree-sitter-go[core]`), so they can resolve to an incompatible combination.
- **Why `tree-sitter-language-pack` was not used.** It requires Python ≥ 3.11, and RepoNeedle supports 3.10.
- **No downloads at parse time.** Nothing is downloaded or compiled while parsing. A grammar is available only if its package is installed.

Check what is available:

```python
from reponeedle.core.tree_sitter_extraction import tree_sitter_status
tree_sitter_status()   # runtime version/error, and per-language availability, grammar version and ABI
```

## 3. Enabling it

```python
from reponeedle import RepoNeedleEngine
from reponeedle.models import AblationConfig

engine = RepoNeedleEngine.from_directory(
    "path/to/repo", ablation_config=AblationConfig(structural_parser="tree_sitter"))
result = engine.retrieve("fix the discount rounding bug", ranker="arm101")
print(engine.function_graph.diagnostics["structural_parser"])
```

You can also construct the graph directly with `FunctionGraphEngine(structural_parser="tree_sitter")`. Both accept only `"regex"` (the default) or `"tree_sitter"`.

## 4. Capability matrix

All languages: comments and string contents are never extracted; Unicode identifiers are supported; line numbers are 1-based start lines; paths are passed through unchanged; output order is source order and deterministic.

| | TypeScript / TSX | Go | Rust | Java | C++ |
| :--- | :--- | :--- | :--- | :--- | :--- |
| File extensions | `.ts` `.mts` `.cts` (`.d.ts`) / `.tsx` | `.go` | `.rs` | `.java` | `.cpp` `.cc` `.cxx` `.hpp` `.hh` `.hxx` `.h` |
| Free functions | `function`, generators, `const f = () =>` / `function` expressions | `func` | `fn` (including nested `fn`) | — | definitions (prototypes excluded) |
| Methods + container | class methods, class-field arrow functions | receiver type of `func (r *T)` | `impl T` / `impl Trait for T` / `trait` | class, interface, enum, record, nested class; constructors | in-class definitions (incl. templates) and `T::m` out-of-class definitions |
| Nested functions | yes (attributed to their own name) | closures → enclosing function | nested `fn` → own name | lambdas / anonymous classes → enclosing method / class | lambdas → enclosing function |
| Imports recorded | named, aliased, default, namespace, side-effect, `import x = require()` | path + alias, `_`, `.` | `use` trees (lists, aliases, globs), `mod x;`, inline `mod` | single-type, static, wildcard | `#include "x"`, `#include <x>` |
| Package / module | — | `package` | — | `package` | — |
| Calls | `f()`, `a.b.f()`, `new C()` | `f()`, `pkg.F()`, `x.M()` | `f()`, `a::b::f()`, `x.m()`, `Self::f()` → impl type | `m()`, `x.m()`, `new C()` | `f()`, `ns::f()`, `x.m()`, `x->m()`, `new T()` |
| Import resolution to files | relative specifiers (`.ts`, `.tsx`, `.d.ts`, `index.*`, `.js`→`.ts`) | `go.mod` module path; without `go.mod`, a unique directory suffix | `crate::`, `self::`, `super::`, sibling modules, the crate's own name (from `Cargo.toml`) for `tests/` | `a.b.C` → unique `…/a/b/C.java` | quoted includes (relative, then unique suffix); diagnostics only |

**Import-bound resolution.** A call is *bound* when its qualifier root (e.g. `fmt` in `fmt.Sprintf`, `ns` in `ns.f()`) or, for an unqualified call, its name, is bound by an import in the same file. Rust `crate::`/`self::`/`super::` paths are treated the same way.
- **Verified edge.** A bound call becomes a `verified_call` edge at **1.0** only if the import resolves to repository files and **exactly one** of them defines the called name. This is the same criterion and confidence the existing resolver uses for a qualified module call.
- **No edge** is created when the import is external (`fmt`, `java.util`, `events`, `<vector>`), cannot be resolved, resolves ambiguously, does not define the name, or the call goes through a deeper member chain (`ns.sub.f()`). Such calls are never passed to the name-based heuristics.
- **Local definitions shadow imports.** An unqualified call to a function defined in the same file stays intra-file.

**Everything else** goes through the unchanged resolver: intra-file calls, Python-style dotted imports, unique global names (0.9), directory-local names (0.75) and unique method names (0.7). In Tree-sitter mode, two narrow adjustments apply to calls from Tree-sitter-parsed files:
- an *unqualified* call is matched by name only against free functions and constructors, not against other files' methods;
- overloads that all live in one file count as one target file.

Edges from such files are deduplicated per (caller file, caller function, target file, target function, edge type). Files that fell back to regex keep the 1.2.0 edge behaviour exactly.

## 5. Fallback and diagnostics

| Situation | Behaviour |
| :--- | :--- |
| `tree-sitter` not installed | Every handled file uses the regex extractor; reason recorded; one `WARNING` on the `reponeedle.function_graph` logger |
| One grammar missing or ABI-incompatible | Only that language falls back; the others are parsed |
| Syntax errors | Tree-sitter returns a partial tree; what it recovered is extracted and the file is listed in `tree_sitter_with_syntax_errors`. Definitions after an error may be lost (§6) |
| Unexpected extraction exception | That file falls back to regex with the exception text as the reason |
| Empty file | No records |
| Unsupported extension | Regex extractor (unchanged) |

`engine.function_graph.diagnostics["structural_parser"]` (Tree-sitter mode only) contains:
- `runtime_available`, `runtime_version`, `runtime_error`;
- `languages` — per language: `tree_sitter_files`, `regex_fallback_files`, `parser_available`, `grammar_version`, `abi_version` or `error`;
- `files` — `tree_sitter`, `tree_sitter_with_syntax_errors`, `regex_fallback` (path → reason), `python_ast`, `regex_other_languages`;
- `imports` — counts by resolution status;
- `calls` — import-bound outcomes: `resolved`, `external`, `unresolved`, `not_defined`, `ambiguous`, `unverifiable`;
- `edges`.

In the default mode no diagnostics key is added.

## 6. Limitations

- **Syntax only.** There is no type information. `obj.method()` on a local variable is resolved, if at all, by the existing name heuristics; Tree-sitter does not know `obj`'s type. Overloads, virtual dispatch, generics, traits and interfaces are not resolved.
- **Rust macros.** Calls inside macro invocations (`println!(…)`, `assert_eq!(…)`) are not extracted, because macro arguments are unparsed token trees.
- **C++.** The `#include` resolution is recorded but does not create call edges, so C++ calls are resolved only by the existing name heuristics. The preprocessor is not run. Constructors invoked through declarations (`T x(1);`) are not recorded as calls. A `ns::f()` definition is treated as a free function only if `ns` is declared as a namespace in the same file; otherwise it is assumed to be a member of `ns`. `.h` files are parsed as C++.
- **TypeScript.** Path aliases (`@/x`, `tsconfig` `paths`), bare package specifiers and `export … from` re-exports are not resolved. A default import resolves to the target file without checking a name. Interface method signatures are not functions.
- **Go.** The import alias defaults to the last path segment; a package whose name differs from its directory (e.g. `gopkg.in/yaml.v3`) needs an explicit alias to be matched. Calls through package-level variables (`pkg.Var.M()`) are not verified.
- **Java.** Wildcard imports and same-package classes are not import-bound (they fall back to the name heuristics). Nested-class imports (`a.B.C`) are not resolved. Abstract and interface methods count as definitions.
- **Partial trees.** Tree-sitter's error recovery can drop definitions after a syntax error (observed for TypeScript, Rust and C++ in the fixtures). Those files are flagged rather than re-extracted with regex.
- **Test files.** These are recognised by the existing path rule (`"test"` in the path), not by attributes such as `#[test]` or `@Test`.
- **Directory indexing.** `from_directory` indexes `.ts`, `.tsx`, `.go`, `.rs`, `.java`, `.c`, `.cpp` and `.h` (unchanged). Other C++ extensions are parsed only when supplied through `from_documents`.
- **Retrieval quality is unvalidated.** No retrieval-quality benchmark has been run with this option. More extracted syntax does not by itself mean better retrieval, and no ranking weight was changed.

## 7. Tests and CI

| File | Requires the extra | Covers |
| :--- | :--- | :--- |
| `tests/test_tree_sitter_extraction.py` | yes | Exact records per fixture file, comments, strings, Unicode, nesting, qualified calls, imports, errors, empty files, determinism |
| `tests/test_tree_sitter_graph.py` | yes | Exact edges per language, import-bound resolution, external and ambiguous imports, duplicates, confidence parity, test-file links, single missing grammar, engine opt-in |
| `tests/test_tree_sitter_fallback.py` | no | 1.2.0 golden for the default mode, Python unchanged, missing runtime, per-file errors, no network, packaging |

Fixtures are in `tests/fixtures/tree_sitter/`. In CI:
- The `tree-sitter-optional` job installs the extra on Linux (Python 3.10, 3.11, 3.12, plus the minimum versions), macOS and Windows, and fails on any skip.
- The `package-install` job installs the built wheel with and without the extra.
- The standard matrix runs without the extra, which verifies the fallback path.
