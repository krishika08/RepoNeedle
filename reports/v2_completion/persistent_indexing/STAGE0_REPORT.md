# V2 Stage 0: Correctness Foundation for Persistent and Incremental Indexing

**Branch:** `feat/v2-persistent-indexing-stage-0`, from `main` at `06d4fe6` (includes PR #22).
**Scope:** Stage 0 of [the persistent-indexing design](../../../docs/PERSISTENT_INDEXING_DESIGN.md) (§15). **There is no persistence:** no SQLite, index cache, `IndexCacheConfig`, artifact serialisation, file watcher or incremental index maintenance. Retrieval scores, rankings, routing, packing, discovery order and every default are unchanged. The package version stays 1.2.0.

## 1. Summary

| Stage 0 item | Result |
| :--- | :--- |
| Function-graph rebuild state | `FunctionGraphEngine.build_graph()` resets every structure derived from the document collection. A rebuild on one instance equals a build on a fresh instance (ordered comparison). |
| Stable cache signatures | The five per-document caches key on SHA-256 over type- and length-framed extractor inputs plus a versioned namespace. Signatures are identical across processes and `PYTHONHASHSEED` values. Extraction results are unchanged. |
| Document removal | `RepoNeedleEngine.remove_documents(paths)`: in memory, refit-based, order-preserving. The result equals a fresh build over the remaining documents. |
| Differential equivalence harness | `tests/index_equivalence.py` compares every index, per-query score arrays, retrieval over all 5 rankers and the CUD-Pack matrix, exactly, against a fresh build. It uses a frozen corpus of **225 queries** (`tests/fixtures/equivalence/queries_v1.json`). |
| Mutation suite | 17 scenario tests covering the 15 required scenarios, plus 3 seeded mutation sequences of 6 steps each, compared with fresh builds after every step. |
| Stage 1 guardrails | The prototype corruption suite now runs on database files **for both encodings, including the selected encoding B** (14/14 and 15/15 corruptions rejected). Artifact identity is verified against a recomputed key. Manifest ordinals are dense. The snapshot helper refuses unsafe archive members without relying on extraction filters. |

Also fixed: `BM25Index.fit([])` and `SubwordSemanticIndex.fit([])` kept the previous fit's state, which `remove_documents()` of every document would have exposed.

## 2. Audit (before any change)

**Baseline:** `main` at `06d4fe6ac4b786ec800ff90b9a60f0ee2a353bb0`, clean working tree, version 1.2.0. The full suite on Python 3.11.9 gave **726 passed, 14 skipped**, with no failures.

### 2.1 Per-document caches and their key inputs

| Cache | Before Stage 0 | Inputs the extractor actually reads | Stage 0 signature |
| :--- | :--- | :--- | :--- |
| `BM25Index._doc_term_cache` | `f"{path}::{len}::{hash(content)}::{','.join(symbols)}"` | path, symbols, full content, `path_weight`, `symbol_weight`, `body_weight`, `decouple_symbols` | `bm25-doc-terms/1` over exactly those |
| `SubwordSemanticIndex._doc_feature_cache` | same | `f"{path} {' '.join(symbols)} {content[:8000]}"`, `min_n`, `max_n` | `semantic-doc-features/1` over exactly those |
| `SelectiveAbstainer._doc_vocab_cache` | same | path, symbols, `content[:3000]` | `abstainer-doc-vocab/1` |
| `FunctionGraphEngine._polyglot_cache` | same (shared with the Tree-sitter cache) | path, content (`symbols` was signed but never read) | `function-graph-polyglot/1` over path, content |
| `FunctionGraphEngine._ts_cache` | same | path (language and `is_test` derive from it), content | `function-graph-tree-sitter/1` over path, content |

The old signatures had three defects:
- **`hash()` of `str` is randomised per process**, so a signature identified nothing outside the process that computed it.
- **`","`-joined symbols were ambiguous:** `["a,b"]` and `["a", "b"]` produced the same signature.
- **Two caches had incomplete inputs:** BM25's per-document weights and the semantic n-gram range were not signed, so mutating those attributes between fits would have reused stale extractions.

**Not changed:** `packer.py` uses `hash()` in three in-process, query-time caches (token counts, legacy focus spans, skeletons). They are not per-document index state and not candidates for persistent reuse, so they were left alone. Their theoretical exposure to 64-bit `hash()` collisions is listed as a limitation (§7).

### 2.2 Derived state per index, and what survived a rebuild

| Index | Derived state | Reset before Stage 0? |
| :--- | :--- | :--- |
| BM25 | `docs`, `doc_paths`, `num_docs`, `avg_doc_len`, `doc_lengths`, `doc_len_norms`, `doc_term_freqs`, `doc_frequencies`, `idf`, `inverted_index` | Yes, except **`fit([])` returned early, leaving `idf`, `doc_lengths`, `doc_len_norms` and `inverted_index` from the previous fit** |
| Semantic | `doc_paths`, `num_docs`, `vocabulary`, `idf`, `doc_matrix`, `_query_cache` | Yes, except **`fit([])` left `vocabulary`, `idf` and `doc_matrix`** |
| RepoGraph | graph, all maps, invocation and degree-matched structures, PageRank | Yes (every map cleared). `num_docs` was only set by `fit()`; it is now initialised |
| FunctionGraph | graph, functions, call sites, edges, file-to-file edges, callers/callees maps | Yes |
| FunctionGraph | **`module_to_path`, `package_to_files`** | **No**: entries from earlier collections survived and produced edges to removed files |
| FunctionGraph | **`diagnostics`** (`structural_parser`, `scip`), **`scip_relationships`**, `_ts_norm_to_path`, `_ts_resolver` | **No** |
| Abstainer | `repo_vocabulary` | Yes |

**Rankers** (`arm101`, `cascade`, `change_impact`, router) hold configuration only; they read the indexes at query time.

### 2.3 Methods that build, refit or replace documents

| Method | Behaviour |
| :--- | :--- |
| `RepoNeedleEngine.__init__` → `_fit(docs)` | De-duplicates by path: first position, last value. Optional polyglot symbol extraction. Fits all five indexes. |
| `from_directory()` / `from_documents()` | Discovery (or the given list), then the constructor |
| `update_document(s)()` | Replaces by path in `path_to_doc`; **new paths are appended**; refits all five indexes over all documents |
| `remove_documents()` (new) | Validates, then `_fit(remaining)`; restores the previous documents if the refit raises |

### 2.4 Ordering dependencies

Document order is an input everywhere:
- list positions in BM25, semantic, RepoGraph and the function graph;
- semantic vocabulary tie order;
- `module_to_path`: last wins (first wins for some short names);
- function-graph edge order, and edge weights (last writer wins);
- NetworkX insertion order before PageRank;
- the dict key order of every map.

`update_documents()` appends new paths, so an addition can differ from a fresh discovery scan (§4.3).

### 2.5 Existing tests that depend on the behaviour touched

| Test | Dependency |
| :--- | :--- |
| `tests/test_v1_1_change_impact_integration.py::test_incremental_indexing_bit_identical_consistency` | in-place `update_documents()` |
| `tests/test_scip_core.py` | `"scip" not in function_graph.diagnostics` without SCIP |
| `tests/test_scip_graph.py` | SCIP edge construction |
| `tests/test_tree_sitter_graph.py` | `diagnostics["structural_parser"]` after a build |
| `tests/test_hf_space_bundle.py` | the bundled package copy must equal `reponeedle/` |

All of them pass unchanged. The bundle in `hf_artifacts/space/` was re-synchronised locally; nothing was uploaded.

## 3. Implementation

### 3.1 Function-graph lifecycle (`reponeedle/core/function_graph.py`)

`_reset_build_state()` runs at the start of every `build_graph()`. It clears:
- the graph, `module_to_path` and `package_to_files`;
- functions, call sites, edges and file-to-file edges;
- the callers and callees maps;
- `scip_relationships`, the Tree-sitter resolver state and `diagnostics`.

**Kept:** configuration, the loaded `scip_index`, and the per-document extraction caches. Those caches are safe to keep because every hit is validated by its signature.

**One subtlety:** the engine records a SCIP "skipped" diagnostic when a requested index cannot be loaded, *before* the first build. That diagnostic is now stored in `scip_load_diagnostics` and re-applied after each reset, so `engine.scip_diagnostics` is unchanged.

### 3.2 Signatures (`reponeedle/core/signatures.py`)

`stable_signature(namespace, *fields)` is SHA-256 over:
- the namespace;
- each field, framed with a one-byte type tag and an 8-byte length.

| Field type | Encoding |
| :--- | :--- |
| `str` | UTF-8 with `surrogatepass` |
| `int` | decimal |
| `float` | `float.hex()` |
| `bool` | its own type tag |
| `None` | its own type tag |
| sequence of `str` | the framed items |

Bytes and non-string sequences are rejected.

Each cache signs exactly the inputs its extractor reads (§2.1), plus a version constant that must be bumped when the extractor's output for the same inputs changes. Inputs an extractor never reads are deliberately not signed. Examples: text beyond the semantic index's 8,000 characters, and `symbols` for the function-graph extractors. Signing them would only cause needless misses.

### 3.3 `remove_documents()` (`reponeedle/engine.py`)

```python
removed = engine.remove_documents(["shop/pricing.py", "web/src/api.ts"])
# -> ["shop/pricing.py", "web/src/api.ts"] in index order; engine.docs keeps the survivors' order

engine.remove_documents([])                  # -> [] (no change)
engine.remove_documents(["a.py", "a.py"])    # removed once
engine.remove_documents("a.py")              # TypeError: pass an iterable of paths
engine.remove_documents(["missing.py"])      # KeyError("not indexed: ['missing.py']"); nothing removed
engine.remove_documents(list(engine.path_to_doc))   # every document: same state as RepoNeedleEngine()
```

- **Path matching** is exact against `FileDoc.path`, with no normalisation; `"shop\\cart.py"` is unknown.
- **Return value:** a list, like other engine methods returning collections. `update_documents()` is unchanged.
- **No document I/O:** no document file is read; a test patches `open`, `os.stat` and `os.walk` to fail. **Exception:** with an opt-in SCIP index, the refit re-runs SCIP resolution, which checks the index's document paths on disk, exactly as every build and `update_documents()` do. Removing a file from the index while it still exists on disk therefore reports it as "not indexed by RepoNeedle" in the SCIP diagnostics, and after deletion as "missing".
- **Not transactional.** Validation happens before any state changes. If the refit raises, the previous documents are refitted before the exception propagates, which a test exercises. If that refit also fails, the engine is inconsistent and must be rebuilt; this is documented.

### 3.4 Differential equivalence harness (`tests/index_equivalence.py`)

**Captures** (index state is taken before any retrieval, because retrieval can insert keys into the function graph's `defaultdict`s):

| Component | What is captured |
| :--- | :--- |
| Documents | order, content digests, every `FileDoc` field, `IndexingDiagnostics` |
| BM25 | configuration and every attribute; arrays by bit pattern; postings as ordered lists |
| Semantic | vocabulary with order, IDF, CSR `indptr`/`indices`/`data` (bit pattern) |
| RepoGraph | nodes and edges with attributes in insertion order, every map, PageRank |
| FunctionGraph | functions, call sites, edges (all fields, ordered), file-to-file edges, graph with weights, callers/callees, module and package maps, diagnostics, SCIP relationships |
| Abstainer | vocabulary and threshold |
| Scores | BM25 and semantic score arrays per query |
| Retrieval | 5 rankers × task types (the full `ranked_files`, every `ScoredFile` field, explanations, abstention diagnostics); the experimental-abstention path; anchored `change_impact` |
| CUD-Pack | selected files (order, tier, tokens, rendered content), total tokens and rendered context, for budgets {512, 2,000, 4,000, 8,192} × {compact, complete} × {`legacy`, `ast_blocks`} |

**Comparison:**
- **Exact.** Dicts are compared in key order, then by values; lists in order; floats and arrays by bit pattern. Sets are compared as sets, because set iteration order is not defined state. Nothing is sorted to make results agree.
- **Located mismatches.** Each report names the component, the key or query, the expected and actual values (floats with `hex()`), the first differing array index, the configuration and the mutation sequence.

**Query corpus:** `queries_v1.json` (version 1, frozen) has 225 queries:

| Category | Queries |
| :--- | ---: |
| identifier | 30 |
| function name | 25 |
| path | 25 |
| natural language | 40 |
| test discovery | 25 |
| stack trace | 15 |
| empty match | 15 |
| out of scope | 15 |
| tie candidates | 10 |
| multi-signal | 15 |
| Unicode | 10 |

A test asserts that the corpus produces at least one exact tie between non-zero BM25 scores.

**Fixture:** `tests/equivalence_fixture.py` is a 31-file repository:
- Python packages and tests;
- duplicate function names and module stems;
- TypeScript, Go (`go.mod`), Rust (`Cargo.toml`) and Java;
- Markdown, YAML, TOML and JSON;
- Unicode identifiers and content;
- a generated module.

## 4. Test results

All results are from local runs on Windows 11. CI results are recorded in the PR.

**New Stage 0 test files** (134 tests):

| File | Tests | Python 3.11 (core) | Python 3.12 (all extras) |
| :--- | ---: | :--- | :--- |
| `tests/test_stage0_function_graph_lifecycle.py` | 12 | 10 passed, 2 skipped (Tree-sitter) | 12 passed |
| `tests/test_stage0_signatures.py` | 45 | 45 passed | 45 passed |
| `tests/test_stage0_remove_documents.py` | 20 | 19 passed, 1 skipped (SCIP) | 20 passed |
| `tests/test_index_equivalence.py` | 26 | 26 passed | 26 passed |
| `tests/test_stage1_readiness_prototype.py` | 31 | 31 passed | 31 passed |

**Mutation checks of the tests themselves:**
- With the two map resets removed from `_reset_build_state()`, 9 of the 10 runnable lifecycle tests fail.
- With the BM25 empty-fit reset removed, the remove-every-document equivalence test fails, with located mismatches in `doc_lengths`, `doc_len_norms` and `idf`.
- Both fixes were restored afterwards.

**A defect found by the extras run.** The SCIP removal scenario first failed on Python 3.12 with protobuf, on two counts:
- SCIP diagnostics contain wall-clock fields (`parse_ms`, `ingest_ms`). The harness now drops `*_ms` keys from diagnostics, the only exclusion besides `execution_time_ms`.
- SCIP resolution checks document paths on disk during every refit. The test removed the file from the index before deleting it, so the two engines saw different disk states. The test now deletes first, as a user would. The `remove_documents()` docstring, the changelog and this report no longer claim that the refit reads nothing when SCIP is enabled.

**Full suites:**

| Run | Result |
| :--- | :--- |
| Baseline `main` `06d4fe6`, Python 3.11.9, core dependencies | 726 passed, 14 skipped |
| This branch, Python 3.11.9, core dependencies | **857 passed, 17 skipped**. Skips: 5 Tree-sitter, 5 SCIP (extras not installed), 7 symlink permission on this host. |
| This branch, Python 3.12.10, all extras: `treesitter` (runtime and the five grammars), `scip` (protobuf) and `mcp` | **1095 passed, 8 skipped**. All 8 skips are symlink permission on this host. `tests/test_public_api.py` was excluded because the local FastAPI 0.110 and Starlette 1.10 are mutually incompatible, so the root demo `api.py` fails to import; that is an environment problem unrelated to this change. |
| Stage 0 tests repeated under `PYTHONHASHSEED=1` and `=987654` (Python 3.11) | 131 passed, 3 skipped in both runs |
| Python 3.10 | not installed locally; covered by the CI matrix |

**Other checks:**
- `actionlint` on the changed workflow: clean.
- The two new test targets in the extras CI jobs (the Tree-sitter job and the SCIP job) run under "any skip fails".

**Harness runtime** (Python 3.11, single runs):

| Test | Time |
| :--- | ---: |
| Full-corpus lifecycle round trip (225 queries × 5 rankers, abstention, anchored change impact, and the CUD-Pack matrix on 19 queries) | about 33 s |
| Task-type matrix (75 queries × 5 rankers × 6 task types: auto and 5 explicit) | about 17 s |
| Each mutation scenario (full index state; 15-query sample with packing) | 2–6 s |
| All five Stage 0 files | 110–150 s |

## 5. Lifecycle parity today

| Operation | Exact parity with a fresh build over ... |
| :--- | :--- |
| `update_documents()` replacing an existing path | the same documents in the same order: **yes** |
| `update_documents()` adding a path | the documents with the new one **appended**: yes. A fresh discovery scan that places it elsewhere: **no**. `test_add_document_diverges_from_a_discovery_ordered_build` asserts that the harness reports this in the document order and the BM25 and semantic state. |
| `remove_documents()` | the remaining documents in their existing order: **yes**, including against a fresh `from_directory()` after the file is deleted |
| Rename (remove + add) | the renamed file appended: yes. At its discovery position: no (as for additions). |
| Repeated full refits; rebuild in another order | yes |
| Remove every document | a never-fitted `RepoNeedleEngine()`: yes |

## 6. Performance

`stage0_benchmark.py`: baseline `06d4fe6` (a temporary `git worktree`) against this branch, on the same inputs. The inputs are a pinned snapshot of this repository (`06d4fe6`, 894 files) and a synthetic 3,000-file repository. Three interleaved rounds ran in fresh subprocesses; the best of the rounds is reported, in seconds. Full data: `stage0_benchmark.json`.

| Measurement | Repository: baseline / Stage 0 | Synthetic 3,000: baseline / Stage 0 |
| :--- | ---: | ---: |
| `lexical` cold fit / warm refit | 4.35 / 3.39; 0.487 / 0.383 | 2.10 / 2.15; 0.198 / 0.253 |
| `semantic` cold fit / warm refit | 12.59 / 15.06; 5.07 / 5.17 | 6.86 / 6.76; 1.44 / 1.49 |
| `abstainer` cold fit / warm refit | 1.16 / 1.77; **0.014 / 0.047** | 2.38 / 2.46; **0.019 / 0.062** |
| `function_graph` cold build / 3 warm rebuilds | 2.75 / 4.69; 1.79 / 2.73 | 3.55 / 3.56; 6.28 / 6.22 |
| `update_documents()`, one file | 9.33 / 5.78 | 4.28 / 4.48 |
| `remove_documents()`: one file / 10% of files (Stage 0 only) | 5.43 / 3.52 | 4.50 / 4.04 |
| Signatures for all documents: SHA-256 / old f-string with `hash()` (Stage 0 process) | 0.015 / 0.004 | 0.060 / 0.005 |

**Readings:**
- **The measurable cost is the signature on warm refits.** Python caches a `str`'s `hash()`, so the old signature was nearly free on a warm refit. SHA-256 over the extractor inputs costs 15 ms for this repository (8 MB) and 60 ms for 3,000 small files. It shows clearly only where the rest of the warm refit is tiny: the abstainer's warm refit grows from about 15 ms to 50–60 ms (3.3–3.5×). Per refit that is at most about 0.06 s per index.
- **Everything else is within this machine's run-to-run noise.** Unchanged code paths moved by −38% to +71% between workloads. For example, the function-graph cold build is 1.71× on the repository and 1.00× on the synthetic repository. `update_documents()` was faster with Stage 0 on the repository (0.62×) and slower on the synthetic one (1.05×). No speedup is claimed from these numbers, and no regression beyond the signature cost is attributed to Stage 0.
- **`remove_documents()` costs a full refit**, about the same as `update_documents()`. That is expected: it is refit-based by design (Stage 0 does not add incremental maintenance).
- **The extraction caches keep working.** Unchanged documents are cache hits after SHA-256: `test_cache_hits_for_unchanged_documents_and_misses_after_changes` counts zero extractor calls on a warm refit and exactly one after an edit, for each of the four caches.

## 7. Known limitations

- **Additions are appended.** `update_documents()` appends new paths, so parity with a fresh discovery scan holds only when the new file sorts last. Stage 0 exposes this and does not change it. Stage 1's `refresh()` rebuilds in discovery order.
- **Refit cost.** `remove_documents()` and `update_documents()` still refit every index (no incremental maintenance); they are faster than a cold build only because of warm per-document caches.
- **`remove_documents()` is not transactional** (§3.3).
- **Per-document caches are never pruned.** Entries for removed or renamed paths stay until the index object is discarded. That costs memory only; a stale entry is never used for another path, because the cache key is the path and every hit is signature-checked.
- **`packer.py` query-time caches still key on `hash(content)`** (in-process only; see §2.1). A 64-bit collision would return a wrong cached span or token count; this was not changed in Stage 0.
- **Harness scope:** a 31-file fixture plus scenario-specific repositories. A sample of queries is used per mutation step; the full 225-query corpus runs on the lifecycle round-trip test and, by thirds, across all task types.
- **Optional extras:** the Tree-sitter and SCIP lifecycle tests run only where those extras are installed (§4).
- **Not measured:** the Stage 1 guardrails cover the research prototype only; Stage 1 must re-establish them in the real implementation.

## 8. Reproducing

```bash
python -m pytest tests/test_stage0_function_graph_lifecycle.py tests/test_stage0_signatures.py \
    tests/test_stage0_remove_documents.py tests/test_index_equivalence.py tests/test_stage1_readiness_prototype.py
python reports/v2_completion/persistent_indexing/stage0_benchmark.py --baseline 06d4fe6 --snapshot 06d4fe6 \
    --rounds 3 --out reports/v2_completion/persistent_indexing/stage0_benchmark.json
python reports/v2_completion/persistent_indexing/sqlite_prototype.py --snapshot bac30c8 \
    --out reports/v2_completion/persistent_indexing/sqlite_prototype.json
```
