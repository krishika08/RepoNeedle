# V2 Milestone 3: AST Block Slicing

**Branch:** `feature/v2-ast-block-slicing`, from `main` at `0c0effe` (includes PR #18).
**Status:** implemented and tested; **opt-in** (`BudgetConfig(focus_span_strategy="ast_blocks")`); not released. The package version stays 1.2.0, and nothing is published.
**User documentation:** [docs/AST_BLOCK_SLICING.md](../../../docs/AST_BLOCK_SLICING.md)

## 0. Summary

**What it does.** CUD-Pack's focus-span tier can now render the smallest **complete** functions, methods, nested functions or top-level declarations that contain query matches, instead of ±3-line windows. Python uses `ast`; TypeScript/TSX, Go, Rust, Java and C++ use Tree-sitter.

**What it keeps.** Each excerpt retains:
- decorators, attributes and annotations;
- attached doc comments;
- relevant imports and the package declaration;
- the headers and closing lines of enclosing classes, impls, namespaces and functions.

All of it is exact source lines with explicit `[lines a-b elided]` markers.

**Fallback.** Everything else falls back per file to the unchanged legacy extractor: other languages, missing parsers, any syntax error, unmatched queries, and oversized blocks.

**Default.** With the default `"legacy"` strategy, focus spans, skeletons and full packs are identical to the baseline packer, checked against a golden snapshot generated from `main`.

**Evidence and claims.**
- On frozen candidate lists, complete blocks used more tokens per file, so compact packs held fewer files.
- No retrieval-quality evaluation was run, and no improvement is claimed.

## 1. Audit (before implementation)

| Component | Finding | Consequence |
| :--- | :--- | :--- |
| `CodeSpanExtractor.extract_focus_span` | Files of 45 lines or fewer are returned whole. Python: `ast` nodes whose **name** contains a term, taking up to 5 nodes and 65 lines from `lineno-1` to `end_lineno+1`; the cap can cut a function. Everything else: a regex line scan with ±3-line windows and a 65-line cap. Imports come from lines in the first 30 starting with `import`, `from`, `package`, `use`, `const` or `var`, which misses grouped Go imports. | The new extractor reuses the 45-line rule and falls back to this function unchanged. |
| `extract_skeleton` | Line-prefix skeleton (Python via `ast`), capped at 280 tokens. | Unchanged; still the oversized and residual tier. |
| `CUDPackOptimizer.pack_context` | Tier choice compares packaged token counts with the remaining budget, and `assert tokens_used <= budget`. | A larger span is simply a larger candidate, so the invariant holds by construction. Only the span source changes. |
| `tree_sitter_extraction.py` | Lazy, cached grammar and parser loading. Records hold `FunctionSymbol.start_line` only, with no end or byte range. | Reused through a new `parse_source()` helper, so there is no second loader. Ranges come from parser nodes, never from `start_line`. |
| `function_graph.py` (Python) | `ast` walk producing `FunctionSymbol(start_line)` for the call graph. | Not reused or changed: it carries no ranges, and graph extraction is out of scope. |
| `tests/test_cud_pack_production.py` | Tier, budget and polyglot checks. The curated and held-out suites need external data. | Unchanged and passing. The suites also drive the packing comparison in §6. |

The proposed interface was written to `docs/AST_BLOCK_SLICING.md` §2 before any code changed.

## 2. Architecture

```
CUDPackOptimizer.pack_context(...)
  └─ config.focus_span_strategy == "ast_blocks"
       └─ CodeSpanExtractor.extract_block_span(content, path, terms)       (result cache: 4,096 / 16 MiB est., §9)
            ├─ empty / <=45 lines ─────────────────► same as legacy
            ├─ analyze_structure(content, path)                            (structure cache: 512 / 32 MiB est., §9)
            │    ├─ .py ── ast ──► _PythonAnalyzer
            │    ├─ .ts/.tsx/.go/.rs/.java/.cpp/... ── tse.parse_source() ──► _TreeSitterAnalyzer
            │    └─ otherwise / no parser / syntax error ──► fallback_reason
            ├─ slice_blocks(...) → attribute matches → rank → select → render
            └─ text is None ──► CodeSpanExtractor.extract_focus_span (legacy, unchanged)
```

**New and changed files.**

| File | Change |
| :--- | :--- |
| `reponeedle/core/block_slicing.py` | **New.** Records, analyzers, selection and rendering. |
| `reponeedle/core/packer.py` | `extract_block_span`, `slice_blocks` and the bounded caches. `pack_context` picks the span source from the config and appends `[ast_blocks: …]` to the explanation of AST spans only. The legacy code paths are untouched. |
| `reponeedle/core/tree_sitter_extraction.py` | `parse_source()`, which `extract()` now also uses (behaviour identical, covered by the existing Tree-sitter golden tests). |
| `reponeedle/models.py` | `BudgetConfig.focus_span_strategy: Literal["legacy", "ast_blocks"] = "legacy"`. |
| HF bundle | The same four files copied (`compare_bundle` returns `[]`). Nothing was uploaded. |

## 3. Extraction behaviour

**Line model.**
- Lines are split on `\r\n`, `\r` and `\n`, exactly like Python's `ast`.
- Tree-sitter node positions are converted from **byte offsets**, which keeps boundaries exact with multibyte text, CRLF and lone CR.
- A node ending at column 0 of the next row (such as `#include` or Rust doc comments) is mapped to its real last line.

**Blocks**, with tested examples:

| Language | Callables | Attached to the block | Scopes (rendered as headers) |
| :--- | :--- | :--- | :--- |
| Python | `def` and `async def` (methods, nested) | decorators, adjacent `#` comments | `class`, enclosing `def` |
| TypeScript/TSX | function and generator declarations, methods, getters, `const f = () => {}`, arrow class fields, `export default function`, top-level callback statements (`describe`/`it`) | `export`, decorators, adjacent comments | class, abstract class, `namespace`, `module`, enclosing functions and callbacks |
| Go | functions, methods, `var f = func() {}` | adjacent comments | enclosing functions |
| Rust | `fn` (free, impl, trait, mod, nested) | `#[...]` attributes, `///` doc comments | `impl`, `trait`, `mod { }` |
| Java | methods, constructors (including inside anonymous classes) | annotations (in modifiers), Javadoc | class, interface, enum, record, annotation type |
| C++ | function definitions (inline, out-of-line `A::f`, in `extern "C"`) | `template <…>`, adjacent comments | class, struct, union, namespace, `extern "C"` |

Non-callable statements directly in a module or class body (constants, fields, structs, interfaces, enums, type aliases) are **declaration** blocks.

**Selection.**
- Each matching line (same substring test as legacy) is attributed to its **innermost** block.
- Blocks are ranked by: distinct terms, then name match, then matching lines, then source order.
- Selection is greedy within 5 blocks and 160 lines.
- A block over 120 lines is never cut: its signature is shown, or the file falls back.

**Rendering.**
- Content: preamble (`package`), relevant imports (bound names used in the output; C/C++ includes, wildcards and `__future__` always kept; at most 25 lines), scope headers and closing lines, and the blocks.
- Order and gaps: everything is in source order. Blank-only gaps are kept verbatim; other gaps become one marker, indented like the code it replaces.

**Fallback reasons** are recorded in `BlockSlice.fallback_reason` and in the packed file's explanation: `unsupported_language`, `parser_unavailable`, `parser_error`, `syntax_error`, `parse_limit`, `no_query_terms`, `no_block_match`, `oversized_block`, `short_file`, `empty_file`.

## 4. Tests

| File | Tests | Needs | Covers |
| :--- | ---: | :--- | :--- |
| `tests/test_block_slicing.py` | 27 | nothing | Python functions, async, methods, nested functions and decorators; matches in bodies; class context; import relevance; deterministic ranking; oversized blocks; line caps; CRLF/CR/multibyte; empty, short and malformed files; JS/C/text fallback; exactness on two **real RepoNeedle modules** (509 and 878 lines); every Python block re-parses with `ast` |
| `tests/test_block_slicing_tree_sitter.py` | 44 | `treesitter` | Hand-checked boundaries for TypeScript, TSX, Go, Rust, Java and C++; closing braces; CRLF invariance; decorators, attributes, annotations, templates, namespaces, impl and test modules; grouped Go imports; multibyte comments; syntax-error fixtures; missing parser (simulated); `parse_source` cache reuse |
| `tests/test_block_slicing_packing.py` | 30 | nothing | **Legacy golden** (282 focus spans, 282 skeletons, 36 packs from the baseline packer at `0c0effe`, for both default and explicit `"legacy"`); budget invariant and exact prompt accounting at 9 budgets (40 to 8,192) × 2 modes × 6 queries; all three tiers still produced; a large block cannot overflow (budgets around its exact size); determinism; cache keys, bounds and parse-once; engine opt-in |

`assert_exact` (in `tests/block_slicing_support.py`) checks every rendered slice line by line. Each output line must be the next source line verbatim, or a single marker whose range is exactly the skipped, non-blank lines. The whole file must be accounted for.

**Local results** (Windows 11):

| Environment | Result |
| :--- | :--- |
| Full suite, Python 3.12.10 with `treesitter` and `scip` | 945 passed, 8 skipped (Windows symlink permission only) |
| Full suite, Python 3.11.9, no extras | 695 passed, 14 skipped (symlink permission and optional extras, including the Tree-sitter block-slicing module) |

**CI.**
- The strict Linux job ("skips fail") now also runs `test_block_slicing.py` and `test_block_slicing_packing.py` without extras.
- The Tree-sitter job runs all three files on six legs: Linux 3.10, 3.11, 3.12 and minimum versions, macOS 3.12, and Windows 3.12.

**PR #19** ([run 44090274632](https://github.com/krishika08/RepoNeedle/actions/runs/44090274632)) passes all 19 checks:
- every Tree-sitter leg: 292 passed, 0 skipped;
- the strict job: 318 passed, 0 skipped;
- Production CI 3.12: 636 passed, 34 skipped (optional extras and external data not installed).

**The first run failed, for two reasons:**
- Sorting fixture `Path`s is case-insensitive on Windows but case-sensitive on Linux, so the golden's candidate order differed between platforms. The order now uses the POSIX path string, and the golden was regenerated from the baseline.
- A `\` line continuation is not valid in the Windows leg's PowerShell.

## 5. Performance

`bench_block_slicing.py` runs on reproducible inputs:
- generated files with 200 or 2,000 functions per language (classes, decorators/attributes, nested functions), queried for one function three quarters of the way down;
- two real modules.

Environment: Windows 11, Python 3.12.10, tree-sitter 0.26.1, median of 5. Raw data is in `benchmark_results.json`.

| Input | Lines | Blocks | AST cold | AST warm (cached) | AST new query | Legacy cold | AST output (lines/tokens) | Legacy output |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Python, 2,000 functions | 18,804 | 4,200 | 178 ms | 0.009 ms | 8.6 ms | 439 ms | 13 / 97 | 12 / 71 |
| TypeScript, 2,000 | 20,603 | 2,000 | 244 ms | 0.029 ms | 40.6 ms | 16.3 ms | 15 / 127 | 12 / 151 |
| Go, 2,000 | 22,007 | 2,000 | 314 ms | 0.043 ms | 27.4 ms | 20.8 ms | 18 / 124 | 10 / 86 |
| Rust, 2,000 | 22,007 | 4,001 | 252 ms | 0.034 ms | 40.5 ms | 11.5 ms | 15 / 115 | 8 / 79 |
| Java, 2,000 | 20,008 | 2,000 | 132 ms | 0.016 ms | 23.7 ms | 13.2 ms | 15 / 109 | 10 / 80 |
| C++, 2,000 | 18,007 | 2,000 | 238 ms | 0.030 ms | 24.3 ms | 17.4 ms | 15 / 114 | 7 / 71 |
| Python, 200 functions | 1,884 | 420 | 10.0 ms | 0.002 ms | 0.9 ms | 12.4 ms | 13 / 97 | 12 / 71 |
| Real: `packer.py` | 509 | 22 | 9.4 ms | 0.006 ms | 0.8 ms | 12.4 ms | 110 / 1,034 | 76 / 718 |
| Real: `function_graph.py` | 878 | 51 | 16.3 ms | 0.005 ms | 1.9 ms | 21.3 ms | 172 / 2,097 | 61 / 606 |

**Speed.**
- Python block slicing was *faster* than the legacy Python path on these inputs; both parse with `ast`.
- Tree-sitter languages cost about 6–15 ms per 1,000 lines cold, of which parsing in C is roughly half. The legacy regex scan costs about 1 ms per 1,000 lines.
- Parsed structures are cached per file, so additional queries cost about 0.5–2 ms per 1,000 lines.

**Optimisation applied during the milestone.** The nested-declaration search skips single-line subtrees and only classifies declaration node types, which cut the TypeScript cold time from about 444 ms to 244 ms.

**Memory.** Peak Python allocation of one cold extraction (tracemalloc) is 62 MB for the 18,804-line Python file, the same as legacy, because `ast` dominates both. For Tree-sitter files it is 15–25 MB at 2,000 functions, against about 1.3 MB for the legacy regex scan.

**Output size.** The synthetic queries select one block. AST output is a complete function with its imports and class header: 97–127 tokens, against 71–151 for legacy windows. On the real modules AST spans are larger (1,034 vs 718 and 2,097 vs 606 tokens) because several complete functions match.

## 6. Packing-level comparison (frozen candidates; not a retrieval evaluation)

`eval_packing_suites.py` packs the **same frozen candidate lists** (top 85) for the 40 annotated queries of the curated (20) and held-out (20) CUD-Pack suites, which cover Go, Rust and Python. It uses the external Agent Retrieval Bench file texts. Raw data is in `packing_suite_results.json`.

| Strategy | Suite | Mode / budget | All gold files packed | All gold symbols visible | Mean files packed | Mean tokens |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: |
| legacy | curated | compact 4,096 | 20/20 | 20/20 | 12.85 | 4,071 |
| ast_blocks | curated | compact 4,096 | 19/20 | 19/20 | 10.10 | 4,077 |
| legacy | held-out | compact 4,096 | 19/20 | 12/20 | 13.10 | 4,066 |
| ast_blocks | held-out | compact 4,096 | 19/20 | 12/20 | 10.45 | 4,076 |
| legacy | curated | complete 8,192 | 18/20 | 18/20 | 8.15 | 8,172 |
| ast_blocks | curated | complete 8,192 | 18/20 | 18/20 | 8.15 | 8,171 |
| legacy | held-out | complete 8,192 | 16/20 | 15/20 | 7.90 | 8,156 |
| ast_blocks | held-out | complete 8,192 | 16/20 | 15/20 | 7.95 | 8,160 |

**Findings.**
1. **Compact mode packs fewer files with complete blocks** (about 10 instead of about 13). In the curated suite, one gold file no longer fits. A variant with tighter caps (80-line blocks, 100 lines in total) gave almost the same result (10.2 files, 18/20 symbols), so the cost comes from completeness, not from the caps.
2. **Most gold files in this corpus are not sliced.** The corpus stores long files **truncated** (the text ends with `...[truncated]`), so they are not valid syntax. The whole-file `syntax_error` fallback then applies: 20 of 22 gold-file focus spans in the curated compact run, and 16 of 23 in the held-out run. Real repository files are complete, so this corpus understates how often slicing applies, and **it cannot show whether AST spans help**.
3. Complete mode is essentially unchanged, because it mostly uses full files and skeletons.

**Conclusion.**
- The evidence does **not** support making `ast_blocks` the default: it costs coverage in compact packs and showed no measured benefit here.
- It stays opt-in.
- A retrieval-level evaluation on complete (untruncated) repositories is needed before any default change.

## 7. Known limitations

1. **No retrieval-quality evaluation.** No improvement is claimed. The packing comparison in §6 uses a fixed ranking and mostly truncated files.
2. **Higher token cost** per file than legacy windows, which reduces the number of files packed in compact mode.
3. **Strict whole-file fallback** on any syntax error. One stray error or a truncated file disables slicing for that file. Error-free blocks before the first error are not used, deliberately.
4. **Lexical relevance** only (substring match of query terms), as in legacy.
5. **Unsupported constructs.**
   - One-line nested functions are attributed to their enclosing function.
   - Anonymous callbacks inside named functions are part of that function.
   - Object-literal methods are not separate blocks.
   - JavaScript and C are not handled.
6. **Tree-sitter cold cost** is about 6–15 ms per 1,000 lines (against about 1 ms for legacy), measured on one Windows machine.
7. **Not exposed in the CLI or MCP tools.** The strategy is selected through `BudgetConfig` in the Python API only.

## 8. Reproducing

```bash
pip install -e ".[dev,treesitter]"
pytest tests/test_block_slicing.py tests/test_block_slicing_tree_sitter.py tests/test_block_slicing_packing.py
python reports/v2_completion/ast_block_slicing/bench_block_slicing.py --out benchmark_results.json
python reports/v2_completion/ast_block_slicing/eval_packing_suites.py          # needs external/agent-retrieval-bench
python reports/v2_completion/ast_block_slicing/make_legacy_golden.py           # regenerates the legacy golden from 0c0effe
python reports/v2_completion/ast_block_slicing/bench_cache.py --out cache_results.json   # §9 cache benchmark
```

## 9. Post-milestone maintenance: bounded cache memory and `cap_lines` (PR #20)

Branch `fix/ast-block-slicing-cache-api`, from `main` at `90efcd2`. Retrieval, ranking, routing, tier selection, AST parsing, language support and the legacy extractor are unchanged; `ast_blocks` stays opt-in.

### 9.1 Problem

- The structure cache (512 entries) and result cache (4,096) were bounded only by **entry count**.
- Both kept the **full file content in their keys**, so every cached file version stayed alive, including versions the caller had already dropped (changed or re-read files).
- `extract_block_span(..., cap_lines=65)` used `cap_lines` only on the legacy fallback, and the result cache ignored it.

### 9.2 Cache design

**Keys.**
- The structure cache is keyed by `(path, SHA-256(content))`; the result cache by `(path, SHA-256(content), frozenset(query terms), cap_lines)`.
- The digest is 32 bytes and no source text is retained.
- A changed file always produces a new key.

**Budgets.** `reponeedle/core/bounded_cache.ByteBudgetLRU` is a deterministic LRU bounded by **entry count and an estimated-byte budget**.

| Cache | Entry limit | Estimated-byte budget |
| :--- | ---: | ---: |
| Structure | 512 | 32 MiB |
| Result | 4,096 | 16 MiB |

Both budgets are configurable per extractor (`structure_cache_bytes`, `span_cache_bytes`) or through class attributes.

**Eviction.**
- After each insert, the oldest entries are evicted until both limits hold.
- Evicted values are dropped, and a test checks with `weakref` that they are released.

**Oversized entries.** An entry estimated at more than **1/8 of its budget** is returned but not cached (counted as `rejected_oversized`).

**Accounting (estimate).** For each entry, `sys.getsizeof` is summed over what it keeps alive, plus a fixed 160-byte per-entry allowance for the LRU slot, link and `(value, size)` pair. The objects counted are:
- the block, scope and import records, now `slots=True` dataclasses so `getsizeof` covers their fields;
- tuples, frozensets and name strings;
- the per-line owner map, and the integers above the small-int cache;
- the rendered text;
- the key's path, digest and terms.

Literals and allocator overhead are excluded. The estimate stands for retained Python objects; it is **not** RSS. `block_cache_stats()` exposes it.

**Calibration.** Against tracemalloc's measured retained allocations (after `gc.collect()`), estimates were:

| Measured scope | Estimate ÷ measured |
| :--- | ---: |
| Single structures (878- to 22,000-line files) | 0.92–1.34 |
| A populated cache of 160 entries | 1.23 |
| The churn workloads below | 0.92 and 1.01 |

A test enforces a 0.5–2× band.

### 9.3 `cap_lines` decision

`cap_lines` is kept and defined as a **soft selection budget** (`Optional[int] = None`).

**At the slicer level** (`slice_blocks(max_total_lines=...)`), the highest-ranked eligible block is always selected **whole**, even if it alone is longer. Further blocks are added only while the total stays within the budget, and no limit ever truncates a block.

**Other behaviour:**
- `max_block_lines` (120) remains a hard eligibility limit, with header-only rendering or the `oversized_block` fallback.
- With `None`, the defaults apply: 160 lines for slicing, and the legacy 65 for the fallback.
- An integer is also passed to the legacy fallback with its legacy meaning.
- Non-positive and non-integer values raise `ValueError`.
- `cap_lines` is part of the result-cache key.

**Why keep it.** It keeps `extract_block_span` a drop-in counterpart of `extract_focus_span`.

**Compatibility.**
- The argument was never in a release: `v1.2.0` has no `extract_block_span`.
- No call site passes it.
- At the default, the only behaviour change is the soft-first-block rule, which matters only when `max_total_lines < max_block_lines` (160 > 120 by default).
- All 282 AST spans (with their selections and notes) and 36 `ast_blocks` packs over the fixture corpus are byte-identical before and after this change.
- The legacy golden (282 spans, 282 skeletons, 36 packs from the baseline packer) is unchanged.

### 9.4 Tests

`tests/test_block_slicing_cache.py` has 31 tests and needs no extras. They cover:
- **LRU:** order, refresh on `get`, byte budget, oversized rejection, size update on replace, invalid limits.
- **Keys:** keys hold the SHA-256 digest and never the content; different paths are cached separately.
- **Correctness:** changed content is never served stale; query-term separation with a shared structure; repeated-query reuse (same object returned).
- **Budgets:** under churn the byte budgets are never exceeded and eviction happens; entry-count limits still apply.
- **Oversized entries:** computed but not retained, and re-parsed on the next call while the small file stays cached.
- **Eviction:** evicted objects are released (`weakref`).
- **Estimates:** the size estimate stays within 0.5–2× of tracemalloc.
- **`cap_lines`:** defaults equal the slicer defaults; caps of 1, 21, 43, 44, 66 and 500 give 1, 1, 1, 2, 3 and 5 complete 22-line blocks; a block longer than the cap is returned whole; the oversized rule is independent of the cap; the cap is part of the key; it reaches the legacy fallback unchanged; invalid values are rejected.

It is added to the strict Linux job and to the six Tree-sitter CI legs.

**Results.**

| Where | Result |
| :--- | :--- |
| Local, Python 3.12 + `treesitter` + `scip` | 976 passed, 8 skipped (Windows symlink permission only) |
| Local, Python 3.11, no extras | 726 passed, 14 skipped |
| Local, optional-extra suites on protobuf 5.29.0 | 444 passed, 1 skipped |

**PR #20 CI** ([run 44100939524](https://github.com/krishika08/RepoNeedle/actions/runs/44100939524)) passes all 19 checks:
- every Tree-sitter leg: 323 passed, 0 skipped;
- the strict job: 349 passed, 0 skipped;
- Production CI 3.12: 667 passed, 34 skipped.

### 9.5 Benchmark (`bench_cache.py`, raw data in `cache_results.json`)

**Environment:** Windows 11, Python 3.12.10. This PR is compared with the baseline caches of `90efcd2`, loaded from git.

**Timing.**
- Method: `time.perf_counter`, median of 9, with the implementations **interleaved within each repeat** to cancel machine drift.
- Machine noise was still about ±30% on cold runs.

| Input (2,000 functions) | Cold: baseline / PR | Warm repeat: baseline / PR | New query on parsed file: baseline / PR | Digest | Size estimate (on insert) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Python (18,804 lines, 477 KB) | 238 / 200 ms | 0.17 / 0.44 ms | 17.0 / 15.7 ms | 0.22 ms | 3.1 ms |
| TypeScript (20,603 lines, 456 KB) | 244 / 262 ms | 0.08 / 0.46 ms | 27.4 / 21.0 ms | 0.38 ms | 2.7 ms |
| Go (22,007 lines, 509 KB) | 328 / 294 ms | 0.09 / 0.48 ms | 27.2 / 19.8 ms | 0.23 ms | 1.4 ms |

**What this shows.**
- Cold and new-query times show no consistent change: the differences are within noise and point both ways.
- A warm cache hit now costs one SHA-256 of the content, about 0.3–0.4 ms more per call for a 500 KB file.
- Inserting a new structure costs one size estimate, 1.4–3.1 ms, against 200–300 ms of parsing.

**Churn: repeated indexing of many different large files.**
- Workload: 300 generated Python, TypeScript and Go files (about 3,000–6,000 lines each, 32 MB of source in total), two queries per file, through one extractor.
- Isolation: each variant runs in a **fresh process**.
- Content lifetime: each file's content is created inside the traced region and dropped by the caller after use, so anything left allocated is held by the cache.

| Variant | Entries kept (structure / result) | Evictions (structure / result) | Rejected oversized | **Measured** retained (tracemalloc) | **Estimated** retained | Traced peak | RSS before → after | ms per file |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline `90efcd2` | 300 / 600 | 0 / 0 | n/a | **120.4 MB** | n/a | 133.7 MB | 73.7 → 211.7 MB | 446 |
| This PR, defaults | 134 / 600 | 166 / 0 | 0 | **34.4 MB** | 34.8 MB | 53.8 MB | 70.8 → 124.6 MB | 476 |
| This PR, 2 MiB + 1 MiB budgets | 10 / 440 | 191 / 160 | 198 | **3.3 MB** | 3.04 MB | 22.8 MB | 70.6 → 89.9 MB | 588 |

**Findings.**
- The baseline kept all 300 structures, and every dropped file's content, alive through its keys.
- With the defaults, the structure cache filled its 32 MiB estimate (33.3 MB estimated) and evicted the oldest 166 structures. Measured retained memory fell by **71%**.
- With the small budgets, the estimate stayed within its 3 MiB, but the **measured** retained figure (3.30 MB) exceeded the budget by about 5%. The budget bounds the estimate, not measured memory.
- Under the small budgets, 198 structures were above 1/8 of the 2 MiB budget, so they were not cached and the second query re-parsed them. That is why this variant was slower per file.
- RSS is shown for context only. It includes the interpreter and parsers, the allocator does not necessarily return freed memory to the OS, and the difference from the baseline (+54 MB against +138 MB growth) is indicative only.

### 9.6 Limitations

- Sizes are estimates. They track tracemalloc within about ±35% here, and measured retained memory can exceed a configured budget slightly.
- The legacy extractor's caches (`_span_cache`, `_skel_cache`) and the tokenizer cache are unchanged and remain unbounded by bytes. AST-mode fallbacks still populate the legacy span cache.
- Warm hits now hash the content (about 0.5–0.8 ms per MB measured).
- No persistent or on-disk cache was added; that is out of scope.
