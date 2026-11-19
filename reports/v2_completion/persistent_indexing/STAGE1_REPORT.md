# V2 Stage 1: Persistent Repository Indexing

**Branch:** `feat/v2-persistent-indexing-stage-1`, from `main` at `cccd91f` (includes the Stage 0 merge, PR #23).
**Scope:** Stage 1 of [the persistent-indexing design](../../../docs/PERSISTENT_INDEXING_DESIGN.md) (§15, §17).
- **Opt-in.** Without `index_cache` nothing changes: no database is opened or created, and the default code path is the same discovery code (refactored into helpers and checked by the Stage 0 harness).
- **Not incremental.** Every global structure is recomputed in full on every start by the existing code. Stage 1 is persistence, not incremental indexing, and claims no incremental behaviour.
- **No retrieval, ranking, routing, packing, token-budget or discovery-order change.** The package version stays 1.2.0.

## 1. Summary

| Requirement | Result |
| :--- | :--- |
| A real SQLite cache is created and a fresh process reuses it | Yes: cold builds publish a generation; warm restarts in fresh interpreters reuse every artifact (§5) |
| Unchanged files reused safely; changed, added, deleted and renamed files handled | Yes: per-file reuse is keyed by the decoded-text digest, the metadata digest, the extractor fingerprint and the Stage 0 input signature (§3) |
| Global structures rebuilt by the existing code paths | Yes: the cached build seeds per-document caches and then calls the unchanged `RepoNeedleEngine._fit()` |
| Retrieval and packing bit-identical to uncached builds | Yes: the Stage 0 harness (225 queries, 5 rankers, abstention, anchored change impact, CUD-Pack matrix) on every scenario, in-process and across processes (§6) |
| `persist_exclude` privacy | Matching files are indexed in memory as usual; nothing derived from them is found in the main database, WAL, SHM or any other cache file, raw, compressed or decoded, including after a purge (§7) |
| Artifact keys include the document-metadata digest | Yes (the research prototype's omission is fixed), plus the extractor's input signature (§3) |
| Checksums and manifest verification in production code | Yes: `reponeedle/core/index_cache/store.py` (§4) |
| Corrupt caches rejected and rebuilt by policy | 20 corruption scenarios plus 7 recovery tests, all rejected as a whole and rebuilt to an equivalent engine; `never` raises; `always` never reads (§8) |
| Crashes never expose partial generations | Five crash points in the writer protocol, each leaving the previous or the complete new generation (§9) |
| Concurrent readers and writers | No torn reads or lost publishes (§9) |
| 10k/30k/100k database measurements | Actual databases: 244.9 MB (10k realistic), 103.6 MB (10k reduced), 311.0 MB (30k reduced). **100k was not measured:** the in-memory engine exceeded this machine's memory (23.2 GB committed of 15.5 GB). The size defaults stay provisional (§10). |

## 2. Baseline and audit

- **Baseline:** `main` at `cccd91f958140fd3996f5c901b74171fe30b0a75`, clean tree, version 1.2.0.
- **Environment:** Python 3.11.9 (SQLite 3.45.1) and 3.12.10 (SQLite 3.49.1) on Windows 11, 18 CPUs, 15.5 GB RAM.
- **Baseline suite** (Python 3.11, a clean worktree of `main`): 833 passed, 23 skipped, 0 failed.

**Per-document caches and what is persisted:**

| Cache | Populated by | Entry | Persisted as (kind) |
| :--- | :--- | :--- | :--- |
| `BM25Index._doc_term_cache` | `fit()` | `(signature, {term: weight}, effective_length)` | `lexical`: ordered terms, float weights, length |
| `SubwordSemanticIndex._doc_feature_cache` | `fit()` | `(signature, {feature: count})` in first-occurrence order | `semantic`: ordered features and counts |
| `SelectiveAbstainer._doc_vocab_cache` | `fit()` | `(signature, set of tokens)` | `abstainer`: sorted tokens (membership-only use) |
| `FunctionGraphEngine._polyglot_cache` | `build_graph()` (regex/AST mode) | `(signature, (functions, call sites, symbols, imports))` | `function_graph`: every dataclass field, in order |
| `FunctionGraphEngine._ts_cache` | `build_graph()` (Tree-sitter mode) | Tree-sitter extraction | **Not persisted in Stage 1** (Stage 4); Tree-sitter builds take the uncached route |
| `FileDoc` metadata | discovery (`_build_file_doc`) | language, `is_test`, line and token counts, symbols, imports | `doc_meta` |

Global structures are rebuilt, never persisted:
- BM25: `doc_frequencies`, IDF, lengths, norms and positional postings;
- semantic: df, vocabulary with tie order, IDF and the normalised CSR matrix (float32);
- RepoGraph: maps, NetworkX insertion order and PageRank;
- function graph: resolution and ordered edges;
- the abstainer's repository vocabulary.

Rebuilding them with the existing code is what makes insertion order and float32 arithmetic identical by construction.

## 3. Architecture

```
reponeedle/core/index_cache/
  paths.py         repository identity, cache location, permissions, network-filesystem detection
  fingerprints.py  extractor, document-metadata, discovery and index fingerprints (with source digests)
  codecs.py        versioned, validated payload codecs (canonical JSON + zlib; no pickle, no eval)
  schema.py        DDL, artifact keys, checksums, canonical manifest digest
  connection.py    writer/reader connections with verified settings
  store.py         verified loading of one generation; writer protocol, GC, quarantine
  session.py       engine integration: cached build and refresh()
```

**Engine integration.**
- **Discovery refactor.** `from_directory()` discovery is split into `_scan_repository()` with a per-file document factory, plus `_build_file_doc()` and `_finish_directory_engine()`. The default path calls the same code in the same order.
- **Cached build.** It uses a factory that rebuilds a `FileDoc` from verified metadata when the decoded-text digest matches. It then seeds the per-document caches and runs the existing `_fit()`.

**Artifact identity.**
- **Key:** `artifact_key = SHA-256(framed("reponeedle-artifact-key-v1", kind, extractor_fp, path, text_sha256, doc_meta_sha256, input_sig))`. `input_sig` is the extractor's Stage 0 signature over its exact inputs and configuration. Framing is length-prefixed, never delimiter-based.
- **Reader:** the key is recomputed from the manifest and the current inputs before reuse. A key whose recomputation differs is never used.

**Fingerprints** (design §7):

| Fingerprint | Covers |
| :--- | :--- |
| Extractor (one per kind) | `ARTIFACT_VERSIONS`, codec, configuration, Python minor version, Unicode database version, and a SHA-256 of the **source code** of every module the extractor runs (line endings normalised), including the codecs. A code change invalidates its artifacts even if no constant is bumped. |
| Document metadata | Decoding semantics, the discovery code (`engine.py`), `models.py`, `graph.py`, the tokenizer, and `enable_polyglot_symbols` |
| Discovery | The effective ignore patterns (defaults, `extra_ignore`, root `.gitignore`), limits, `pathspec` version, case-sensitivity |
| Index | All of the above, the global parameters and the global-assembly sources. Recorded; Stage 1 recomputes globals anyway |

**Invalidation is per kind.** A changed extractor fingerprint re-extracts only that kind. When a metadata-fingerprint change leaves the metadata values unchanged, the other kinds stay reusable because their keys use the metadata *digest*. The tests change each fingerprint input and assert exactly which artifacts are re-written (§6).

## 4. SQLite schema, integrity and protocol

**Tables** (`schema.py`):
- `meta`, `generations`, `manifest` (dense ordinals), `excluded`;
- `artifacts` with `input_sig` and `checksum`;
- `file_artifacts` with deferred foreign keys;
- `global_state` (a checksummed summary), `optional_components`.

`provides` and `consumes` are not created; they belong to Stage 2.

**Integrity:**
- **Artifact checksum:** binds key, kind, extractor fingerprint, path, input signature, codec and payload.
- **Global-state checksum:** binds name, generation, codec and payload.
- **Manifest digest:** a versioned digest over the manifest, `file_artifacts`, `excluded` and `optional_components` rows, sorted by primary key and bound to the generation id.
- **Reader** (`load_generation`): runs in one read transaction and verifies application id, schema version, repository identity, the published generation, the manifest digest, global state, path syntax, dense ordinals, and every referenced artifact's identity, key, checksum and decodability, plus document metadata against its manifest columns. **Any failure rejects the whole database.**

**Connections:**
- `isolation_level=None`; every setting is applied outside transactions and read back.
- Writer: WAL, `synchronous=FULL` for its whole lifetime, foreign keys, busy timeout, `secure_delete`, incremental auto-vacuum on new files, and `fullfsync` on macOS.
- Mismatched settings disable persistence for the run. Under `never` they raise.

**Writer protocol:**
1. A `building` generation marker.
2. Artifact batches (`INSERT OR IGNORE`, 2,500 rows each).
3. A size check against `max_db_bytes`.
4. **One publish transaction:**
   - replace the published rows;
   - re-insert any referenced artifact that a concurrent writer's GC removed;
   - write the manifest digest and the summary;
   - supersede the previous generation and move `current_generation`.
5. GC of unreferenced artifacts, except those of live `building` generations.
6. Incremental vacuum and `wal_checkpoint(TRUNCATE)`.
7. `max_total_bytes` enforcement across the cache directory, which never deletes a database in use.

## 5. Test results

**New Stage 1 test files** (134 tests):

| File | Tests | Covers |
| :--- | ---: | :--- |
| `tests/test_stage1_cache_units.py` | 58 | Codecs (exact round trips, canonical encoding, 14 malformed payloads, decompression limits); artifact keys covering every input; checksum binding of every column; manifest digest (order-independent, generation-bound); fingerprints (configuration, version constants, source digests, line-ending normalisation); configuration validation; repository identity; links refused; POSIX permissions; writer settings verification; static checks (no PRAGMA inside transactions, no pickle/eval) |
| `tests/test_stage1_cache_lifecycle.py` | 30 | The 20 lifecycle scenarios through the public API, plus policies, defaults, optional components and the full-corpus warm restart |
| `tests/test_stage1_cache_corruption.py` | 27 | 20 corruption scenarios with all three policies, plus 7 recovery tests |
| `tests/test_stage1_cache_processes.py` | 15 | Fresh-process warm restarts (including the full 225-query corpus), 5 crash points, a writer killed holding the lock, concurrent readers and writers, lock waits and timeouts, a postponed checkpoint, and the hash-seed finding (§6) |
| `tests/test_stage1_persist_exclude.py` | 4 | Privacy (§7) |

**Local runs (Windows 11):**

| Run | Result |
| :--- | :--- |
| Baseline `main` `cccd91f`, Python 3.11.9 | 833 passed, 23 skipped |
| This branch, Python 3.11.9 (final commit) | **989 passed, 19 skipped, 0 failed** |
| This branch, Python 3.12.10 with the `scip` and `mcp` extras: Stage 1 suites, bundle and Stage 0 removal tests | **170 passed, 2 skipped** (symlink, POSIX permissions) |

The 19 skips are:
- 10 for the missing Tree-sitter and SCIP extras in this venv. CI runs those. Locally, Windows Application Control blocks the Tree-sitter native extension, so Tree-sitter could only be validated in CI;
- 8 for Windows symlink and POSIX-permission tests;
- 1 for the MCP symlink test.

**CI** (all 24 checks pass): the production matrix on Python 3.10, 3.11 and 3.12 (full suite), the Tree-sitter and SCIP jobs (including the uncached-route test), and a new **persistent index cache** job:

| Platform | Python | SQLite | Strict (skips fail) |
| :--- | :--- | :--- | :---: |
| Linux | 3.10.22 | 3.46.1 | yes |
| Linux | 3.12.16 | 3.46.1 | yes |
| macOS | 3.12.10 | 3.49.1 (`fullfsync` verified) | yes |
| Windows | 3.10.11 | **3.40.1** | no (POSIX-permission test skips) |
| Windows | 3.12.10 | 3.49.1 | no (POSIX-permission test skips) |

The minimum supported SQLite version is set from this evidence to **3.40.1**, the lowest version on which the full Stage 1 suite passed. Older libraries disable persistence with a diagnostic; the in-memory build is unaffected.

## 6. Exact equivalence

**Coverage.** Every lifecycle, corruption, crash, concurrency and privacy test compares the cached engine with a fresh uncached `from_directory()` using the Stage 0 harness:
- document order and metadata;
- BM25 state and postings;
- semantic vocabulary and CSR arrays (bit-exact);
- RepoGraph and FunctionGraph structures in insertion order;
- the abstainer vocabulary;
- all five rankers;
- abstention diagnostics and anchored change impact;
- the CUD-Pack matrix (4 budgets × 2 modes × 2 focus-span strategies).

The full **225-query** corpus runs on a warm restart in the same process and in a separate process, and on the Stage 0 lifecycle round trip.

**There are no disagreements.**

**Cross-process comparisons need the same hash seed.** RepoNeedle iterates sets of strings in several places, *without any cache*:
- BM25 document frequencies;
- class-to-test invocation edges;
- the symbol a change-impact explanation cites.

So two **uncached** builds in different processes with different `PYTHONHASHSEED` values differ in dict order and in some explanation texts. `test_uncached_builds_already_differ_across_hash_seeds` pins this behaviour.

Cross-process tests therefore build the warm cached engine and the uncached reference in separate child processes with the same seed. This is a property of the existing retrieval code, not of the cache. It is reported here rather than changed, because fixing it would change retrieval code.

## 7. `persist_exclude` privacy

A test file contains unique markers: a constant, a function name, a class name, an import and its path. The scanner searches every file in the cache directory (main database, WAL, SHM, any other file) for these forms of the markers, path and decoded-text digest (raw and hex):
- the raw bytes;
- **every decodable zlib stream at every byte offset**, which covers stale pages;
- every artifact payload, decoded through the production codecs.

It is first shown to find them while the file is persisted.

| Case | Result |
| :--- | :--- |
| Excluded from the start | Nothing found; ordinals dense `0..n-2`; retrieval identical to a fresh build, cold and warm; the file is re-extracted on every start |
| **Persisted, then excluded** | The five artifacts are collected (`secure_delete`, incremental vacuum, `wal_checkpoint(TRUNCATE)`). Nothing found in any cache file; ordinals dense; retrieval identical |
| Matching file skipped for size | No `excluded` row reveals its path |

This is not a forensic-erasure claim about the storage medium.

## 8. Corruption and recovery

All of the following are handled by the **production** reader:

| Scenario | Rejected by |
| :--- | :--- |
| Main database truncated; page bytes changed | SQLite errors |
| A payload byte flipped inside the file | checksum |
| Re-encoded but valid payload; swapped payloads | checksum |
| Artifact `kind` or `path` changed | identity |
| Extractor fingerprint changed; forged key (consistent in both tables) | key recomputation, manifest digest |
| Document-metadata digest changed; mapping deleted | manifest digest |
| Referenced artifact deleted | missing |
| Generation id changed; generation unpublished | not published |
| Global state changed | global checksum |
| Application id changed | application id |
| Unsupported schema version | schema |
| Repository root changed | identity |
| Path traversal in the manifest | digest |

For each:
- `never` raises `IndexCacheError` with the reason;
- `auto` sets the database aside (`<name>.corrupt-<UTC>`), rebuilds an equivalent engine, and the rebuilt cache is reusable on the next start.

**Further recovery tests:**
- `always` never reads a corrupt cache, and replaces a file that is not a database.
- A locked database is never set aside.
- Garbage WAL/SHM sidecars never change results.
- A database copied without its WAL is a consistent earlier state.
- A decompression bomb and non-zlib payloads are rejected.
- One bad artifact makes `load_generation` fail as a whole (no partial reuse).

## 9. Crashes and concurrency

**Crash injection** (the child process calls `os._exit` at each point):

| Point | After restart |
| :--- | :--- |
| After the `building` marker | previous generation, intact |
| After the first artifact batch | previous generation, intact |
| Inside the publish transaction, before COMMIT | previous generation, intact |
| After publish, before GC | complete new generation |
| Inside GC, before COMMIT | complete new generation |

**Concurrency:**
- In every case the surviving generation loads under `rebuild_policy="never"` and is equivalent to a fresh build.
- A writer killed while holding the write lock does not block the next writer.
- Two writers each published three generations while three readers each made 25 verified loads: **all six publishes happened (generation 7), and no load ever failed verification**.
- A writer waits for a held lock and then publishes. With a short `busy_timeout`, the run reports `not_persisted` ("database is locked") and the in-memory engine is still exact.
- A checkpoint with an open reader is postponed and reported; the reader keeps its snapshot of the previous generation.

## 10. Database size and performance

`stage1_benchmark.py` (reproducible, seeded) builds synthetic repositories and measures each phase in a fresh process; full data is in `stage1_benchmark.json`.

**Workload profiles:**
- **realistic:** file sizes are log-normal with this repository's measured median (6.4 KB) and spread (p90 17.7 KB), capped at 200 KB. The language mix is py/ts/md/json/go/rs/java. Identifiers come from a Zipf-distributed pool, so vocabulary grows with the corpus, and there are cross-file imports.
- **reduced:** the same generator with files one sixth the size. It exists only because RepoNeedle's **in-memory** index needs about 70× the source size in RAM, so realistic corpora above about 10k files do not fit in this machine's 15.5 GB. Its file sizes are not representative; it measures database growth and SQLite behaviour at large file counts.

The machine was not otherwise idle: other applications held several GB of RAM. Each phase ran once.

**Workloads**

| Run | Files | Source | Mean | p50 | p90 | p99 | Max |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| realistic 1000 files | 1,000 | 9.2 MB | 9,236 B | 6,612 B | 18,778 B | 50,753 B | 73,746 B |
| realistic 2500 files | 2,500 | 22.7 MB | 9,071 B | 6,798 B | 18,053 B | 42,175 B | 87,670 B |
| realistic 10000 files | 10,000 | 89.4 MB | 8,940 B | 6,615 B | 17,844 B | 41,173 B | 141,016 B |
| reduced 10000 files | 10,000 | 15.5 MB | 1,546 B | 1,140 B | 2,984 B | 7,340 B | 23,922 B |
| reduced 30000 files | 30,000 | 46.2 MB | 1,538 B | 1,140 B | 3,002 B | 7,050 B | 33,463 B |
| reduced 100000 files | 100,000 | stopped (see below) | | | | | |

**Time to a ready engine** (fresh process per phase; single run each)

| Run | Uncached | Cold cached (writes the cache) | Warm restart | Restart after 1% modified | Warm vs uncached |
| :--- | ---: | ---: | ---: | ---: | ---: |
| realistic 1000 files | 34.5 s | 40.7 s | 16.9 s | 17.4 s | 2.03x |
| realistic 2500 files | 140.6 s | 155.2 s | 84.9 s | 80.6 s | 1.66x |
| realistic 10000 files | 2,607.3 s | 2,405.2 s | 2,825.2 s | 4,098.7 s | 0.92x |
| reduced 10000 files | 187.5 s | 218.6 s | 142.2 s | 117.8 s | 1.32x |
| reduced 30000 files | 1,154.5 s | 1,581.1 s | 1,325.4 s | 820.2 s | 0.87x |
| reduced 100000 files | stopped: out of memory (see below) | not run | not run | not run | - |

**Warm-restart phases** (seconds) **and memory**

| Run | Load + verify artifacts | Scan, read, hash | of which hashing | Seed caches | Global fit (existing code) | Persist | Peak RSS uncached / warm | Peak WAL (cold build) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| realistic 1000 files | 3.0 | 0.9 | 0.02 | 0.24 | 12.6 | 0.17 | 0.88 GB / 0.96 GB | 12.3 MB |
| realistic 2500 files | 7.5 | 3.1 | 0.06 | 0.49 | 73.1 | 0.61 | 2.05 GB / 2.23 GB | 12.5 MB |
| realistic 10000 files | 43.1 | 14.8 | 0.21 | 1.98 | 2745.8 | 15.42 | 6.31 GB / 6.12 GB | 14.3 MB |
| reduced 10000 files | 21.2 | 26.4 | 0.42 | 2.40 | 82.5 | 9.70 | 2.95 GB / 3.20 GB | 9.7 MB |
| reduced 30000 files | 77.9 | 52.3 | 0.53 | 7.32 | 1147.7 | 39.28 | 6.68 GB / 6.44 GB | 29.3 MB |

**Actual database size** (after the cold build, checkpointed)

| Run | Database file | x source | Payload: semantic / lexical / abstainer / function graph / doc_meta | Key, checksum and path metadata | Free pages | WAL after |
| :--- | ---: | ---: | :--- | ---: | ---: | ---: |
| realistic 1000 files | 24.7 MB | 2.68 | 14.0 MB / 2.5 MB / 1.1 MB / 2.0 MB / 0.4 MB | 0.8 MB | 0 | 0 |
| realistic 2500 files | 61.9 MB | 2.73 | 35.1 MB / 6.2 MB / 2.8 MB / 4.9 MB / 1.0 MB | 2.1 MB | 0 | 0 |
| realistic 10000 files | 244.9 MB | 2.74 | 138.9 MB / 24.2 MB / 11.2 MB / 19.2 MB / 3.8 MB | 8.4 MB | 0 | 0 |
| reduced 10000 files | 103.6 MB | 6.70 | 50.0 MB / 6.8 MB / 5.3 MB / 4.2 MB / 1.6 MB | 8.4 MB | 0 | 0 |
| reduced 30000 files | 311.0 MB | 6.74 | 149.7 MB / 20.2 MB / 15.7 MB / 12.5 MB / 4.9 MB | 25.2 MB | 0 | 0 |

**Readings:**
- **Stage 1 restarts are faster for small and medium repositories, and the gain shrinks with size.** The warm restart is 2.03× faster than an uncached build at 1,000 realistic files, 1.66× at 2,500, and 1.32× at 10,000 reduced files. At 10,000 realistic and 30,000 reduced files it was **not** faster (0.92× and 0.87×), and those runs were paging (see below).
- **The global fit dominates warm restarts at every size.** It takes 12.6 s of 16.9 s at 1,000 files and 73 s of 85 s at 2,500. Stage 1 recomputes it in full by design.
- **The global fit is superlinear.** Timing each index's warm refit (global work only) at 1,000 and 2,500 realistic files shows where:

  | Index | 1,000 files | 2,500 files |
  | :--- | ---: | ---: |
  | Function graph (global call resolution) | 7.5 s | 50.4 s (about N^2.1) |
  | Semantic | 7.3 s | 19.7 s |
  | RepoGraph | 2.2 s | 6.4 s |
  | BM25 | 1.1 s | 3.1 s |
  | Abstainer | 0.1 s | 0.2 s |

  This is existing behaviour of code Stage 1 must not change, and it is the main Stage 2 target.
- **The 10,000-file realistic and 30,000-file reduced timings are not clean measurements.** During those phases the process had about 7 GB committed while Windows compressed and paged memory (3.5 GB free, 0.6 GB resident at one point). An *unchanged* code path, the global fit, took 2,320 s in the cold build and 3,991 s in the 1%-modified restart. Likewise, in the 30,000-file reduced run (about 1 GB of RAM free), the global fit took 1,148 s in the warm restart and 645 s in the 1%-modified restart. These numbers are reported because they were measured, not as the cache's cost.
- **Cache overhead on a cold build** is 10–18% where the run was not paging (40.7 s vs 34.5 s; 155 s vs 141 s; 219 s vs 187 s). Most of it is payload encoding (JSON + zlib level 1).
- **Loading and verifying artifacts** costs 3.0 s per 1,000 realistic files (43 s at 10,000). That includes a checksum and full decode of every payload; SHA-256 of the decoded text is negligible (0.02–0.4 s).
- **Database size** is a stable **2.7× the source** for realistic files (24.7 MB, 61.9 MB, 244.9 MB at 1k, 2.5k and 10k files) and 6.7× for the reduced profile (103.6 MB at 10k, 311.0 MB at 30k files). In the reduced profile, per-row metadata (keys, checksums, paths: 8.4 MB per 10,000 files) and SQLite page overhead weigh more relative to small payloads. Semantic n-gram counts are about 57% of the realistic database.
- **WAL:** the peak WAL during a cold build stayed between 10 and 29 MB at every size. Artifacts are written in bounded batches (2,500 rows), so their share of the WAL is bounded. The publish transaction carries every manifest and `file_artifacts` row, so its share grows with the file count (14 MB at 10,000 realistic files, 29 MB at 30,000 reduced files). The WAL is truncated to 0 after each build.
- **Size limits stay provisional.** A linear extrapolation of the realistic profile to 100,000 files (an *estimate*, not a measurement) is about 2.45 GB, *above* the provisional 2 GiB `max_db_bytes` default. On this machine, though, the in-memory engine itself cannot build a realistic 100,000-file corpus: at about 70× the source in RAM it would need roughly 60 GB. The defaults are therefore not changed and remain provisional. Above the limit, the documented behaviour applies: nothing is published and the previous generation is kept.

**10k, 30k and 100k files: what was and was not measured.**

| Size | Realistic profile | Reduced profile |
| :--- | :--- | :--- |
| 10,000 files | **Measured:** database 244.9 MB. Timings measured but paging-affected. | **Measured:** database 103.6 MB, all phases |
| 30,000 files | **Not run.** An extrapolation from measured memory (6.3 GB at 10,000 files) exceeds this machine. | **Measured:** database 311.0 MB. Timings measured but paging-affected. |
| 100,000 files | **Not run** (same reason) | **Stopped.** After 18 minutes of the *uncached* build, the in-memory engine had 23.2 GB committed on a 15.5 GB machine (4.3 GB resident, 0.9 GB free): continuous paging. The run was stopped manually and recorded. No 100,000-file database was built. |

The 100,000-file run was stopped by hand, not by the watchdog. The watchdog checked the working set, which physical memory caps; it now also checks committed memory. The blocker is RepoNeedle's in-memory index, which exists with or without the cache. A machine with substantially more RAM is needed to measure Stage 1 at 100,000 files; the command in §13 reproduces the run. Until then, the `max_db_bytes`/`max_total_bytes` defaults remain **provisional**, and every 100,000-file figure in this report is an estimate.

**Optional components.** The Tree-sitter structural parser and SCIP ingestion are not persisted in Stage 1, and their artifact sizes were not measured. Builds with them take the uncached route.

## 11. Known limitations

- **Not incremental.** Every global structure is recomputed on every start, and at 10,000 realistic files the global fit dominates restart time. Stage 1 alone is not a large-repository speedup.
- **`validation="stat"` runs as `"content"`.** Stage 1 reads every file eagerly, so stat validation would save only the hashing time, which is negligible.
- **Optional components** (Tree-sitter, SCIP) are not persisted; those builds are uncached (Stage 4).
- **Cross-process determinism.** Several pre-existing code paths iterate sets of strings, so dict orders and some explanation texts differ between processes with different hash seeds, with or without a cache (§6). Not changed in Stage 1.
- **Network-filesystem detection** is best-effort (Windows drive type, Linux mount table); macOS network volumes are not detected.
- **Purging excluded files.** `persist_exclude` purging relies on SQLite `secure_delete`, incremental vacuum and WAL truncation. It is not a guarantee about the physical storage medium.
- **Size limits** remain provisional (§10). `max_total_bytes` enforcement deletes least-recently-modified *other* databases that are not in use, and is best-effort.
- **Measurement gaps.** The 30k and 100k measurements are limited as described in §10, and the 10k realistic timings are affected by paging.

## 12. Remaining Stage 2+ work

- **Function graph:** dependency-scoped re-resolution (design §9.1–9.2). It is the dominant and superlinear global cost measured here.
- **BM25:** df and IDF bookkeeping, with global O(N) parts labelled (§9.5).
- **Semantic:** vocabulary maintenance, only if bit-identical (Stage 3).
- **Persisting global state** with checksums (the table exists), and the `provides`/`consumes` dependency index.
- **Stage 4:** Tree-sitter and SCIP artifacts, CLI/MCP cache flags, and `cache info/clear/verify` commands.

## 13. Reproducing

```bash
python -m pytest tests/test_stage1_cache_units.py tests/test_stage1_cache_lifecycle.py \
    tests/test_stage1_cache_corruption.py tests/test_stage1_cache_processes.py tests/test_stage1_persist_exclude.py
D=reports/v2_completion/persistent_indexing
python $D/stage1_benchmark.py --files 1000 2500 10000 --profile realistic --out $D/stage1_benchmark.json
python $D/stage1_benchmark.py --files 10000 30000 100000 --profile reduced --phase-timeout-s 7200 --out $D/stage1_benchmark.json
```

## 14. Confirmations

- Persistence is opt-in; without `index_cache` no database is opened or created.
- Global structures are fully recomputed; **no incremental indexing is implemented or claimed**.
- No raw source text is stored. Per-file derived data is stored for files not matched by `persist_exclude`.
- No retrieval, ranking, routing, packing, token-budget or discovery-order behaviour changed.
- The package version is still 1.2.0.
- No release, tag, PyPI publish, Hugging Face upload or Render deployment. The bundled Space package copy was re-synchronised locally only.
