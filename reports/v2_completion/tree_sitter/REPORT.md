# V2 Milestone 2A: Tree-sitter Multi-Language Structural Extraction

**Branch:** `feature/v2-tree-sitter-integration`, from `main` at `d10ee70` (includes PR #15)
**Status:** implemented and tested; opt-in; not released. The package version stays 1.2.0, and nothing is published.
**Scope:** syntax-aware extraction for the function-level call graph. This is **not semantic code intelligence**, and **SCIP ingestion is not part of this milestone**.

| Language | Extraction | Import-bound resolution to repository files | Evidence |
| :--- | :--- | :--- | :--- |
| TypeScript (`.ts`, `.mts`, `.cts`, `.d.ts`) | Supported and tested | Relative specifiers | Fixture + unit tests |
| TSX (`.tsx`) | Supported and tested | Relative specifiers | Fixture + unit tests |
| Go | Supported and tested | `go.mod` module path; directory suffix without `go.mod` | Fixture + unit tests |
| Rust | Supported and tested | `crate`/`self`/`super`, sibling modules, crate name | Fixture + unit tests |
| Java | Supported and tested | Single-type and static imports | Fixture + unit tests |
| C++ (`.cpp`, `.cc`, `.cxx`, `.hpp`, `.hh`, `.hxx`, `.h`) | Supported and tested | Includes recorded; **no call edges from includes** | Fixture + unit tests |
| Python | Unchanged (`ast`) | Unchanged | 1.2.0 golden |
| JavaScript, C | **Not supported** by this path (regex, unchanged) | — | Routing test |

## 1. Dependency research and decision

All facts below were checked against PyPI metadata on 2026-11-16, then confirmed by actual installation and parsing.

| Package | Latest | Python | Wheels (this release) | `[core]` extra declares | Last upload |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `tree-sitter` | 0.26.1 | ≥3.10 | cp310–cp314: Windows (amd64, arm64), Linux (glibc x86_64/aarch64/riscv64, musl x86_64), macOS | — | 2026-11-09 |
| `tree-sitter-typescript` | 0.23.2 | ≥3.9 | abi3: Windows, Linux (glibc, musl x86_64), macOS | `tree-sitter~=0.23` | 2024-11-11 |
| `tree-sitter-go` | 0.25.0 | ≥3.10 | abi3: Windows, Linux (glibc, musl), macOS | `tree-sitter~=0.24` | 2025-08-29 |
| `tree-sitter-rust` | 0.24.2 | ≥3.9 | abi3: Windows, Linux (glibc, musl), macOS | `tree-sitter~=0.22` | 2026-03-27 |
| `tree-sitter-java` | 0.23.5 | ≥3.9 | abi3: Windows, Linux (glibc, musl x86_64), macOS | `tree-sitter~=0.22` | 2024-12-21 |
| `tree-sitter-cpp` | 0.23.4 | ≥3.9 | abi3: Windows, Linux (glibc, musl x86_64), macOS | `tree-sitter~=0.22` | 2024-11-11 |
| `tree-sitter-language-pack` | 1.25.2 | **≥3.11** | cp311-abi3 | `tree-sitter>=0.23` | 2026-11-15 |
| `tree-sitter-languages` | 1.10.2 | — | cp37–cp312 | unpinned `tree-sitter` | 2024-02-04 |

All runtime and grammar packages above are published by the Tree-sitter project, apart from the two bundles in the last rows.

**Rejected:**
- `tree-sitter-language-pack` requires Python ≥ 3.11, which would drop RepoNeedle's supported 3.10.
- `tree-sitter-languages` has had no release since February 2024, has no wheels for newer Pythons, and targets the pre-0.22 binding API.

**ABI compatibility, measured** with the latest grammars installed without `[core]`, on Windows with Python 3.12.10 (`abi_probe.py`):

| Runtime | Runtime accepts ABI | TypeScript / TSX (ABI 14) | Go 0.25.0 (ABI 15) | Rust 0.24.2 (ABI 15) | Java (ABI 14) | C++ (ABI 14) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0.23.2 | 13–14 | parses | **`Incompatible Language version 15`** | **same error** | parses | parses |
| 0.24.0 | 13–14 | parses | **same error** | **same error** | parses | parses |
| 0.25.2 | 13–15 | parses | parses | parses | parses | parses |
| 0.26.1 | 13–15 | parses | parses | parses | parses | parses |

Python 3.11.9 with runtimes 0.25.2 and 0.26.1 gave the same result for all six languages.

**Conflict found.** `tree-sitter-rust[core]` (`~=0.22`) and `tree-sitter-go[core]` (`~=0.24`) both permit runtimes that cannot load these ABI-15 grammars. Installing the grammars with `[core]` alongside a constraint below 0.25 therefore produces a broken combination.

**Decision:** an optional `treesitter` extra with bounded, tested ranges, and no `[core]` extras:

```toml
treesitter = [
    "tree-sitter>=0.25.2,<0.27",
    "tree-sitter-typescript>=0.23.2,<0.24",
    "tree-sitter-go>=0.25.0,<0.26",
    "tree-sitter-rust>=0.24.2,<0.25",
    "tree-sitter-java>=0.23.5,<0.24",
    "tree-sitter-cpp>=0.23.4,<0.24",
]
```

- **Lower bounds** are the tested versions. CI also tests these lower bounds on Python 3.10 (the minimum-versions job).
- **Upper bounds** stop at the next minor version, because grammar node types can change between minor releases.

**Footprint and runtime behaviour:**
- **Download:** about 1.0 MB of wheels on Windows (amd64) and 1.7 MB on Linux (x86_64). Installed size is 8.3 MB on Windows: the runtime is 0.26 MB, and the grammars are C++ 3.43 MB, TypeScript 2.86 MB, Rust 1.13 MB, Java 0.43 MB and Go 0.23 MB.
- **Wheels only.** Prebuilt wheels exist for every target platform, so no compiler is needed; CI installs with `--only-binary`.
- **No downloads.** Nothing is fetched at parse time. A test patches `socket` to fail and parses every corpus successfully.
- **No core dependency.** The core dependencies are unchanged, and a test asserts that tree-sitter never enters the core dependencies or any other extra.

## 2. Architecture

```
FileDoc ──► FunctionGraphEngine.build_graph(structural_parser=...)
              │
              ├── .py ............................ extract_python_ast        (unchanged)
              ├── regex mode / other languages ... extract_polyglot          (unchanged)
              └── tree_sitter mode, handled ext .. tree_sitter_extraction.extract
                     │  lazy load of runtime + grammar (cached per process; failures recorded)
                     │  _Walker: syntax tree → FunctionSymbol / CallSite / ImportRecord (source order)
                     └─ unavailable / error → per-file fallback to extract_polyglot (reason recorded)
              │
              ├── ImportResolver: ImportRecord → repository files (TS, Go, Rust, Java, C++ rules)
              └── call resolution:
                     import-bound call → verified edge (1.0) iff exactly one resolved file defines the
                                          name; otherwise no edge
                     everything else   → existing steps A–E (unchanged confidences)
```

| Component | Role |
| :--- | :--- |
| `reponeedle/core/tree_sitter_extraction.py` (new) | Language detection (single extension map), lazy parser loading, per-language syntax-tree walkers, `ImportRecord`, `ImportResolver`, `tree_sitter_status()` |
| `reponeedle/core/function_graph.py` | `structural_parser` option (default `"regex"`). Tree-sitter extraction loop with its own cache and diagnostics; import-bound resolution; edge deduplication for Tree-sitter-parsed callers |
| `reponeedle/models.py` | `AblationConfig.structural_parser: Literal["regex", "tree_sitter"] = "regex"` |
| `reponeedle/engine.py` | Passes `AblationConfig.structural_parser` to the function graph |

`CallSite` gains `qualifier_path: Optional[str] = None`, a defaulted field set only by the Tree-sitter extractor. It holds `"a.b"` for member access and `"a::b::"` for path-qualified calls, so that Rust `self::f()` and `self.f()` remain distinct.

**Consumers.** The function graph is read only by the opt-in `arm101` ranker. The default `legacy` ranker, `bm25`, `cascade`, `change_impact`, `RepoGraph` (repository graph and PageRank), CUD-Pack (including focus spans), abstention, the MCP tools and the CLI are not modified.

`RepoGraph.extract_polyglot_symbols`, which feeds default retrieval, was deliberately left unchanged. Changing it would alter default rankings and the benchmark baselines, which need a separately reviewed retrieval experiment.

**Resolution rules in Tree-sitter mode** (detailed in [docs/TREE_SITTER.md](../../../docs/TREE_SITTER.md) §4):
- **Import-bound calls.** A call whose qualifier root (or, for an unqualified call, whose name) is bound by an import in the same file is resolved through that import only, as are Rust `crate::`/`self::`/`super::` paths.
  - **Verified edge (1.0):** the import resolves to repository files and exactly one of them defines the called name. This is the criterion and confidence the existing resolver already uses for qualified module calls.
  - **No edge:** the import is external, unresolved, ambiguous or doesn't define the name, or the call goes through a deeper member chain (`ns.sub.f()`). Such calls are never passed to the name heuristics.
- **All other calls** use the unchanged steps A–E, with two narrow adjustments that apply only to callers parsed by Tree-sitter:
  - An unqualified call is matched by unique name only against free functions and constructors. Tree-sitter also extracts methods, which the regex never did; without this restriction, a test's `describe()` would match `Cart.describe` in another file.
  - Overloads that all live in one file count as one target file (Java and C++ constructors).
- **Deduplication.** Edges from Tree-sitter-parsed callers are deduplicated per (caller file, caller function, target file, target function, edge type). Callers that fell back to regex keep the 1.2.0 edge behaviour exactly, including its duplicates.
- **Python** is identical in both modes.

## 3. Per-language extraction

The full matrix is in [docs/TREE_SITTER.md §4](../../../docs/TREE_SITTER.md#4-capability-matrix). Every item there has a test. Fixture outcomes, all asserted exactly by `tests/test_tree_sitter_extraction.py`:

| Corpus | Files | Functions | Calls | Imports | Syntax-error file |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `typescript/` (TS + TSX) | 7 handled | 12 | 24 | 9 | `src/broken.ts` (recovered `ok`; lost 2 later functions) |
| `go/` | 6 handled (+`go.mod`) | 13 | 16 | 4 | `broken.go` (recovered all 3) |
| `rust/` | 7 handled (+`Cargo.toml`) | 15 | 16 | 9 | `src/broken.rs` (recovered `good`, `after`; lost `bad`) |
| `java/` | 5 handled | 16 | 19 | 8 | `Broken.java` (recovered all 3) |
| `cpp/` | 7 handled | 10 | 12 | 7 | `src/broken.cpp` (recovered `good`; lost 2) |

**Every fixture contains:**
- comments and strings holding fake declarations and code-like calls (none extracted);
- a Unicode identifier (`Größe`/`größe`, with the correct line);
- an empty file;
- a syntax-error file;
- a test file;
- cross-file dependencies.

**Language-specific cases also covered:**
- TypeScript: nested functions, arrow functions and class fields, generators.
- Go: closures, receivers, `_` and `.` imports.
- Rust: `impl`/`trait` membership, `Self::` mapping to the impl type, `mod`/`use` trees, and macro bodies (not extracted).
- Java: overloaded constructors, nested and anonymous classes, enum and record methods, and static/wildcard imports.
- C++: in-class templates, out-of-class `T::m`, namespaces, `->` calls and destructors.

## 4. Graph correctness

`tests/test_tree_sitter_graph.py` asserts the exact edge set per language (`EXPECTED_EDGES`), with these results:

| Corpus | Default (regex) edges | Tree-sitter edges | Tree-sitter `verified_call` (1.0) | Other edges (unchanged heuristics) |
| :--- | :--- | :--- | :--- | :--- |
| TypeScript | 5 (incl. 1 duplicate) | 10 | 7 | 3 × `unique_global_call` 0.9 |
| Go | 4 | 5 | 2 | 3 × 0.9 |
| Rust | 2 | 5 | 4 | 1 × 0.9 |
| Java | 0 | 6 | 3 | 3 × 0.9 |
| C++ | 0 | 5 | 0 | 5 × 0.9 |

**Each of the following is a passing test:**
- **Aliased imports name the real target** (`round as roundValue` resolves to `round`).
- **Package aliases work** (Go `pr "…/pricing"`).
- **Rust paths resolve:** `use` items, `use crate::util` plus `util::round2()`, `crate::pricing::apply_discount()`, `self::`/`super::`, and integration tests' `use shop::…`.
- **Java static and type imports resolve, and same-name classes are disambiguated** by the import only.
- **External imports never produce edges,** even when a repository function shares the name.
- **Unresolvable, not-defined and deeper-chain imports produce no edge,** and are counted.
- **Duplicate names across files are not resolved by name.**
- **Local definitions shadow imports.**
- **There are no duplicate edges, and graphs are deterministic.**
- **Each language's test file links to the code it exercises.**
- **Confidence never changes from parsing alone.** For calls not bound by imports, edge type and confidence equal the regex mode's wherever both modes find the edge. Every 1.0 edge comes from a resolved import binding.

## 5. Default behaviour unchanged

- **Regex golden.** `tests/fixtures/tree_sitter/regex_mode_golden.json` was produced by the **unmodified `function_graph.py` from `d10ee70`** (`make_regex_golden.py`). It covers every file's extraction and every edge for all six corpora, Python included. The current default mode reproduces it exactly.
- **Python** extraction and edges are identical in both modes, and `extract_python_ast` output is pinned.
- **Defaults:**
  - `AblationConfig().structural_parser == "regex"`;
  - `RepoNeedleEngine().function_graph.structural_parser == "regex"`;
  - regex mode adds no diagnostics key.
- **Opting in without the packages:**
  - edges and retrieval (`legacy` and `arm101`) match the default exactly;
  - each file's reason is recorded, and one warning is logged.
- **No import overhead:** importing `reponeedle` does not import `tree_sitter`, and that is tested in a fresh process.
- **Hugging Face bundle.** The Space's bundled engine (`hf_artifacts/space/reponeedle/`) was re-synchronised with the root package, as `tests/test_hf_space_bundle.py` requires. The demo never opts in, so its behaviour is unchanged.

## 6. Test results

### Local (Windows 11, 10.0.26200)

| Run | Result |
| :--- | :--- |
| Full suite **with** the extra: Python 3.12.10, tree-sitter 0.26.1 and the 5 grammars | **693 passed**, 7 skipped (Windows symlink permission) |
| Full suite **without** the extra: Python 3.11.9 | **574 passed**, 9 skipped (7 symlink permission, plus 2 tree-sitter-only modules skipped visibly) |
| New tests | 82 extraction + 37 graph + 42 fallback/packaging = **161** |
| CI's Tree-sitter job suite with `REPONEEDLE_FAIL_ON_SKIP=1` (Python 3.12, with the extra) | **191 passed, 0 skipped** |
| Existing function-graph, integration and packer tests (`test_stage3_11`, `_19`, `_20`, `_21`, `test_cud_pack_production`) | 38 passed |
| Build: `python -m build` (sdist + wheel), `twine check --strict` | PASSED. The wheel declares the `treesitter` extra with the bounded ranges, contains `tree_sitter_extraction.py` and no fixtures. Version 1.2.0 (local build; not published) |
| Clean wheel install, **no extra** (`install_smoke.py absent`) | OK: 10/10 handled files fell back with a reason, a warning was logged, edges equal the default mode, and retrieval works |
| Clean wheel install **with `[treesitter]`** (`install_smoke.py present`, `--only-binary`) | OK: it installed exactly the 6 tested wheels, all 10 files parsed, and the verified edges for TypeScript, Go, Rust and Java plus the C++ edge were present |
| `actionlint` (`ci.yml`, `release.yml`) | No issues |

### CI

CI results are recorded in the pull request. CI adds:
- a `tree-sitter-optional` job, which fails on any skip:

  | Platform | Python |
  | :--- | :--- |
  | Linux | 3.10, 3.11, 3.12, and 3.10 with the minimum versions (runtime 0.25.2) |
  | macOS | 3.12 |
  | Windows | 3.12 |

- a `package-install` job: the wheel installed with and without the extra in fresh environments;
- `tests/test_tree_sitter_fallback.py` in the strict Linux job.

The standard 3.10–3.12 matrix runs without the extra, so it exercises the fallback path.

## 7. Performance

`bench_extraction.py --copies 40 --repeats 5` was run on Windows 11 with an Intel64 Family 6 Model 170 CPU, Python 3.12.10, tree-sitter 0.26.1. Results are in `benchmark_results.json`. The corpus is every fixture file replicated 40× (synthetic code; indicative only). Times are medians.

| Language | Files | KiB | Tree-sitter ms | Regex ms | Tree-sitter ms/KiB | Regex ms/KiB |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| TypeScript/TSX | 280 | 75.3 | 39.8 | 4.4 | 0.53 | 0.06 |
| Go | 240 | 53.9 | 22.8 | 5.4 | 0.42 | 0.10 |
| Rust | 280 | 67.3 | 29.3 | 4.0 | 0.44 | 0.06 |
| Java | 200 | 81.6 | 26.7 | 8.0 | 0.33 | 0.10 |
| C++ | 280 | 62.5 | 27.6 | 0.2 | 0.44 | 0.004 (the regex extracts nothing for C++) |

| `build_graph`, 1,360 files across 5 languages | Regex | Tree-sitter |
| :--- | :--- | :--- |
| Cold (new engine, includes extraction) | 36 ms | 210 ms |
| Repeated (same engine; per-file extraction cache hit) | 11 ms | 57 ms |
| Peak Python allocations (`tracemalloc`; excludes Tree-sitter's C memory) | 2.7 MB | 5.6 MB |
| Peak process RSS before → after the build | 79 → 86 MB | 88 → 98 MB |

- **Startup** in a fresh process:
  - `import reponeedle`: 544 ms;
  - plus the runtime and the Go grammar: 538 ms;
  - plus all six grammars: 548 ms.

  Grammar loading is within noise.
- **Cost.** Tree-sitter extraction costs about 4–8× the regex extractor per KiB, roughly 0.15 ms per file on this corpus. Graph construction is about 6× slower cold and 5× repeated.
- **Edge counts on the replicated corpus aren't meaningful.** Every name occurs 40 times, so name-based resolution cannot fire. Edge correctness is measured on the single-copy fixtures (§4).
- **Retrieval quality was not measured.** More extracted syntax is not evidence of better retrieval. No benchmark baseline or ranking weight was changed; a retrieval experiment with the `arm101` ranker would be a separate, reviewed study.

## 8. Known limitations

These are documented in [docs/TREE_SITTER.md §6](../../../docs/TREE_SITTER.md#6-limitations). In summary:
- syntax only: no types, overloads, dispatch or generics;
- Rust macro bodies are not parsed;
- C++ includes give no call edges, there is no preprocessing, constructors invoked through declarations are missed, and `ns::f` definitions use a namespace heuristic;
- TypeScript path aliases and re-exports are not resolved;
- Go package names that differ from their directory need an alias;
- Java wildcard and same-package imports fall back to the heuristics;
- partial trees can lose definitions after a syntax error;
- test files are detected by path;
- `from_directory` indexes only `.cpp` and `.h` among C++ extensions;
- no retrieval-quality validation has been done.

## 9. Reproduction

```bash
git checkout feature/v2-tree-sitter-integration
pip install -e ".[dev,treesitter]"
REPONEEDLE_FAIL_ON_SKIP=1 pytest -q -rs tests/test_tree_sitter_extraction.py tests/test_tree_sitter_graph.py tests/test_tree_sitter_fallback.py
pytest -q                                                    # full suite
python reports/v2_completion/tree_sitter/bench_extraction.py --copies 40 --repeats 5
python reports/v2_completion/tree_sitter/install_smoke.py present   # after installing the wheel with [treesitter]
python reports/v2_completion/tree_sitter/abi_probe.py               # runtime/grammar ABI check

# Regenerate the 1.2.0 regex golden from the reference implementation:
git show d10ee704f4f0ae73145a35ac0f376f3c99ee30ca:reponeedle/core/function_graph.py > fg_reference.py
python reports/v2_completion/tree_sitter/make_regex_golden.py fg_reference.py tests/fixtures/tree_sitter/regex_mode_golden.json
```

## 10. Not done in this milestone

These are out of scope:
- SCIP ingestion;
- AST block slicing or any CUD-Pack or focus-span change;
- dynamic dependency tracking;
- persistent indexing;
- an Aider adapter;
- calibrated abstention;
- retrieval-quality benchmarking;
- any release, tag, PyPI, Hugging Face or Render action.
