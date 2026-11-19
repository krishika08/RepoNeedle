# V2 Stage 2: Dependency-Scoped Graph Re-Resolution and Incremental Bookkeeping

**Scope:** design sections 9.1–9.5 and the Stage 2 row of section 15 ([PERSISTENT_INDEXING_DESIGN.md](../../../docs/PERSISTENT_INDEXING_DESIGN.md), §18 "Stage 2 as built"), plus two hardening fixes to the Stage 1 cache.
**Base:** `main` at `c5b1e028538e53779e959d000c69f4ee0333248a` (Stage 1, PR #24). **Package version:** `1.2.0` (unchanged).
**Baseline for comparisons:** the Stage 1 implementation commit `9cb4c4614014dbdd4c85606d7fd3f91baf623762`, run from a separate worktree on the same machine.

## 1. Summary
- **Graph resolution is now limited to affected files.** A cached build re-resolves only the files whose own inputs
  changed plus every consumer of a typed lookup key whose ordered provider list changed. Every other file's stored
  edges are replayed in the current discovery order, after its dependency context is recomputed from the current
  build and verified. A one-file body edit re-resolves 1 file (62 of 51,729 calls at 1,000 files); an unchanged
  restart resolves none; adding a second definition of a widely called function re-resolves exactly its callers.
  PageRank and the other global graph quantities are recomputed in full and reported as such.
- **The dominant Stage 1 cost is gone in every build, cached or not.** The function-graph resolver scanned every
  class and method for each unresolved attribute call (about N^2). It now uses lookup indexes built once per build,
  and RepoGraph caches its per-document class-to-test extraction. A warm function-graph rebuild at 1,000 files takes
  0.45 s instead of 13.3 s. Outputs are identical to verbatim copies of the previous implementation.
- **Measured restarts** (median of rounds, fresh processes, Stage 1 at `9cb4c46` on the same machine):

  | Workload | Stage 1 warm restart | Stage 2 warm restart | Stage 2 restart after a one-file edit |
  | :--- | ---: | ---: | ---: |
  | 1,000 realistic files | 32.3 s | 17.4 s (1.86×) | 17.5 s (Stage 1: 42.2 s) |
  | 2,500 realistic files | 138.9 s | 50.7 s (2.74×) | 50.5 s (Stage 1: 141.8 s) |
  | 10,000 reduced files (clean round) | 42.7 s | 30.7 s (1.39×) | 30.2 s (Stage 1: 40.7 s) |

  Uncached builds are faster too (1.29× and 1.65× at 1,000 and 2,500 realistic files), because the resolver change
  applies to them. Larger corpora: §8.5.
- **Global work now dominates.** The semantic refit (Stage 3) and loading and verifying every artifact take most of a
  Stage 2 restart; after the resolver change, re-resolving even 20,000 calls costs about a second, so wall time hardly
  depends on the size of the change.
- **Bookkeeping:** BM25 is partially incremental for an in-process `refresh()` with an unchanged document set and
  order (2–3.6× faster than refitting BM25); a warm restart refits it because its dictionary order depends on the
  per-process hash seed. Abstainer vocabulary from reference counts. The semantic index is recomputed in full.
- **Schema version 2** with stable file ids (never reused, never given to `persist_exclude`d files), migrated in
  place from Stage 1 caches, with every Stage 1 artifact reused.
- **Two Stage 1 safety issues fixed:** size-limit eviction could delete a database another process was reading, and a
  privacy purge could be reported complete while stale pages remained.
- **Exact equivalence** with fresh uncached builds after every mutation (in-process refresh and warm restart),
  across processes, on the full 225-query corpus, and in every verified benchmark round. 223 new tests; full suite
  and CI results in §6.
- **Not done or not better:** an in-process `refresh()` is slower than a fresh-process restart (it re-verifies the
  whole generation); dependency-context verification costs about as much as indexed resolution, so reuse saves little
  wall time at these sizes; the 100,000-file corpus is still not measurable on this machine (§8.5).

## 2. Stage 1 cache-safety audit and hardening

### 2.1 Eviction could delete a database in use

**Finding.** `store.enforce_total_limit()` opened each candidate database, ran `BEGIN EXCLUSIVE`, rolled back, closed
it and then deleted the database and its sidecars. In WAL mode `BEGIN EXCLUSIVE` does not wait for or detect readers,
and nothing protected the window between the probe and the deletion, so another process's live database could be
deleted.

**Fix** (`lease.py`, `store.enforce_total_limit`, `session.build`):
- every process that opens a cache database (to load or to write) first takes a **shared** operating-system file
  lock on `<database>.lease` and holds it until its connections are closed: POSIX `fcntl.flock`, Windows `LockFileEx`
  through `ctypes` (standard library only);
- eviction takes the **exclusive** lock without waiting and deletes the database, WAL and SHM only while holding it;
  databases in use are skipped and reported ("N other cache database(s) over max_total_bytes were in use and were
  kept"), so the limit may stay exceeded;
- the operating system releases the locks of a process that exits or is killed (no PID records, nothing to go
  stale); lock files are never deleted, because deleting one another process is about to lock would let two
  processes hold "exclusive" locks on different files with the same name;
- a reader that starts while an evictor holds the exclusive lock waits (up to `busy_timeout_s`) and then finds no
  database and builds a new one.

**Tests** (`tests/test_stage2_cache_safety.py`, subprocesses): a shared lease blocks the exclusive one until its
process is killed; shared leases coexist; eviction keeps a database held by a live reader (open read snapshot) and
by a live writer (open write lock), and deletes it (with WAL and SHM) once the holder is gone; a reader starting
during an eviction waits and then builds a correct new cache; lease files are never deleted.

### 2.2 A privacy purge could be reported complete while stale pages remained

**Finding.** When a persisted file became `persist_exclude`d, the publish removed its rows and garbage collection its
artifacts (`secure_delete=ON`), but `wal_checkpoint(TRUNCATE)` cannot complete while another connection holds an older
read snapshot. The old pages then remain in the database file and the WAL, yet the build reported a normal publish
(only a generic "checkpoint postponed" note).

**Fix** (`store.CacheWriter.publish/maintain`, `session._persist`): the publish transaction records
`meta.purge_pending='1'` whenever a previously persisted path is now excluded (or a purge was already pending). After
garbage collection and incremental vacuum, `wal_checkpoint(TRUNCATE)` runs **without waiting** (busy timeout 0 for that
statement only). The purge is reported `complete` only when that checkpoint backfilled every frame and truncated the
WAL; the marker is then cleared. Otherwise the report says `privacy_purge="pending"` with the reason, the marker stays
in the database, and any later writer (`refresh()` or a cached start) completes it. Read-only clients report a
pending purge too. This is not a guarantee about the physical storage medium.

**Tests:** with a reader holding an old snapshot, excluding the marker file reports `pending` (and the marker is
durable); after the reader closes, `refresh()` reports `complete` and the scanner (raw bytes, every zlib stream and
every decoded payload of the database, WAL, SHM and all other cache files) finds no trace of the file's path, digest
or tokens. A later unrelated start also completes a pending purge.

### 2.3 Guarantees kept

Every Stage 1 suite runs unchanged except the artifact counts, which now include the four Stage 2 kinds, and one
message (`not persisted (Stage 4)`). Cache failures still never change the in-memory result.

## 3. Architecture

The full description is design §18; this section summarises what runs where.

### 3.1 Build flow (`reponeedle/core/index_cache/session.py`)

1. Take a **shared cache-use lease** (`lease.py`) for as long as the database is used.
2. Load and verify the published generation in one read snapshot (Stage 1 checks, plus file ids, `next_file_id` and
   the global-state rows). A version-1 database is migrated in place first (writers only).
3. Scan in the unchanged discovery order; reuse verified document metadata.
4. Seed the per-document caches (BM25, semantic, abstainer, function-graph extraction, RepoGraph class-to-test facts)
   where the artifact key recomputed from the current inputs matches; an in-process cache entry that already has the
   current signature is kept as is.
5. `engine._fit(docs, assembly=CachedAssembly(...))`, in the existing order:

   | Stage | Path | Label |
   | :--- | :--- | :--- |
   | BM25 | in-process update when paths and order are unchanged; otherwise `fit()` | `partially_incremental` / `recomputed_in_full` |
   | Semantic | `fit()` | `recomputed_in_full` (Stage 3) |
   | Provider index | stored `provides` events where the key matches, else derived | (work counters) |
   | RepoGraph import edges | affected files resolved, the rest replayed after context verification | `incremental` / `fallback_full` / `recomputed_in_full` |
   | RepoGraph maps and replay, test links, class-to-test, degree-matched control, PageRank | in full | `recomputed_in_full` |
   | Function-graph call resolution | affected callers resolved, the rest replayed after context verification | `incremental` / `fallback_full` / `recomputed_in_full` |
   | Function-graph maps and replay | in full (O(N + F + E)) | `recomputed_in_full` |
   | Abstainer | reference counts by delta | `incremental` / `recomputed_in_full` |

6. Write new artifacts, then publish one generation (file ids allocated in the publish transaction), collect garbage,
   vacuum and checkpoint (purge-aware), and enforce `max_total_bytes` under eviction leases.

### 3.2 Persisted data (schema version 2)

| Kind | Content | Identity (`input_sig`) |
| :--- | :--- | :--- |
| `doc_meta`, `lexical`, `semantic`, `abstainer`, `function_graph` | as Stage 1 | as Stage 1 |
| `repo_graph_facts` | class catalog entries (production files) or invocation candidates (test files), in discovery order | the facts signature (path, `is_test`, content) |
| `provides` | the file's typed provider events for both graphs, in emission order | the function-graph extraction signature |
| `fg_edges` | the caller file's resolved edges + sorted consumed keys | extraction signature + **dependency context** |
| `rg_edges` | the file's import edges + sorted consumed keys | **dependency context** |
| global `abstainer.refcounts/<fp>` | token → persisted documents containing it | bound to the generation and the abstainer fingerprint |

Every artifact key also binds the kind, the extractor fingerprint (version constants, configuration, Python and
Unicode versions, and the source digest of every module involved), the path, the decoded-text digest and the
document-metadata digest; every row carries the Stage 1 checksum.

### 3.3 Stable file ids

`manifest.file_id` is unique and covered by the manifest digest; `meta.next_file_id` is monotonic. Ids are allocated
in the publish transaction from the rows published at that moment, so two writers never allocate the same id, a path
keeps its id through edits and reordering, and a new, renamed or re-added path gets a new id. `persist_exclude`d files
never get one. The loader rejects a manifest entry without an id and a `next_file_id` that would reuse one.

### 3.4 Typed keys, affected files and replay

The key inventory (12 families) and the algorithm are in design §18.2–18.3. In short: a file is re-resolved when its
own inputs changed or it consumed a key whose ordered provider list changed; every other file's stored edges are
replayed only if its dependency context, recomputed from the current build, matches the one bound into its artifact.
Replaying every file's edges in the current discovery order reproduces the maps, edge lists, NetworkX insertion
order and `add_edge` weight overwrites exactly; PageRank and the other global quantities are then recomputed.

**Uniqueness semantics** are captured by the value of `fg.func:<name>` (every definition, with multiplicity) and
`fg.meth:<name>` (the set of files defining the method): adding a second definition, or deleting one of two, changes
the key, so every consumer is re-resolved (tested in both directions, for functions and class methods).

## 4. Incremental bookkeeping

### 4.1 BM25: partially incremental, in-process only

`incremental.bm25_update` brings a fitted `BM25Index` to exactly the state `fit(docs)` would produce.

| Quantity | Modified documents, same paths and order (in-process `refresh()`) | Additions, deletions, reordering, warm restart |
| :--- | :--- | :--- |
| term counts, effective lengths | replaced for changed documents (**incremental**) | `fit()` |
| `doc_frequencies` | ±1 for the symmetric difference of each changed document's term sets (**incremental**) | `fit()` |
| `idf` | recomputed only for terms whose df changed; N is unchanged (**incremental**) | every term (`fit()`, `idf_recomputed_full`) |
| postings | only the changed documents' entries, found by binary search (**incremental**; O(length of each touched posting list)) | rebuilt (`postings_rebuilt_full`) |
| dictionary insertion order | first-seen order rebuilt only for affected first-document groups (term-SET order for `doc_frequencies`/`idf`, term-DICT order for postings) | `fit()` |
| `avg_doc_len`, `doc_len_norms` | **global**: float32 `np.mean` and every norm recomputed by `fit()`'s own expressions whenever a length changed | `fit()` |

**Why a warm restart refits.** `fit()` inserts terms into `doc_frequencies` while iterating each document's term
*set*, whose order depends on Python's per-process string-hash seed. A persisted copy of the dictionary would carry
the order of the process that wrote it, so it could not reproduce a fresh build's dictionary order in another
process (the Stage 0 harness compares dictionary order). BM25 global state is therefore not persisted (design §18.8),
and positional postings never are.

**Exactness evidence** (`tests/test_stage2_bookkeeping.py`): 25 seeded sequences of 15 edit steps each, with edits
designed to move terms between first-seen documents (removing another document's words, introducing words first seen
elsewhere, rewriting documents), compared after every step with `BM25Index().fit(docs)`: arrays bit for bit,
`doc_frequencies`, `idf` and `inverted_index` **including key order**, ordered postings, and `score()` arrays. The
full-fit fallbacks (add, delete, reorder, empty) and the counters are tested too.

**Measured benefit:** see §8 (in-process refresh after a one-file edit).

### 4.2 Abstainer reference counts

The global-state row `abstainer.refcounts/<abstainer fingerprint>` (checksummed, bound to the generation) holds
`token -> number of persisted documents containing it`. A build subtracts the previous vocabularies of deleted or
changed files (from their verified previous artifacts) and adds the new ones; a token leaves the vocabulary when its
count reaches zero. `repo_vocabulary` is the set of tokens with a positive count plus the vocabularies of
`persist_exclude`d documents, which are never counted. Missing or inconsistent counts fall back to a recount.
`fit()` equality (as a set: the abstainer only tests membership) is tested for shared tokens, deletion of one of
several providers and of the last provider, modified files, reordering, empty repositories, repeated identical
builds and 12 seeded random sequences. The abstention heuristic and its confidence are unchanged.

## 5. Full-build resolver optimisation (all builds)

**Profile of the Stage 1 bottleneck** (1,000 realistic files, warm refit of each index on the same instance, this
machine): function graph 11.7–13.3 s, semantic 9.4 s, RepoGraph 2.6 s, BM25 1.5 s, abstainer 0.1 s. In the function
graph, all time was in the resolution loop itself: for each of 7,257 module-qualified Go calls, step E scanned every
method of every class (about 31 million comparisons at 1,000 files), and steps A and B scanned function lists per call.
In RepoGraph, 95% of the time was `_extract_class_to_test_linkages` re-parsing every non-test Python file with `ast`.

**Change.** Lookup indexes built once per build, in the same order as the scans they replace (design §18.1), and the
per-document class-to-test extraction moved into a signature-validated cache (`repo_graph_facts`). The same
uniqueness rules, winners, edge order, confidences, edge types, map insertion orders and weight overwrites result.

| 1,000 realistic files, warm rebuild on one instance | 1.2.0 / Stage 1 code | Stage 2 code |
| :--- | ---: | ---: |
| Function graph | 13.3 s | 0.45 s (0.47 s tracked) |
| RepoGraph | 3.0 s | 0.13 s |

**Exactness:** `tests/test_stage2_resolvers.py` compares both graphs with verbatim copies of the previous
implementation (`tests/reference_v120_function_graph.py`, `tests/reference_v120_graph.py`, from commit `c5b1e02`) on
the equivalence fixture, the synthetic Stage 2 repository (in two discovery orders) and 12 seeded random document sets
with heavily shared names, for four function-graph configurations (structural edges on and off, `min_confidence`
0.0, 0.6 and 0.8) and class-to-test linkage on and off, tracked and untracked, plus refits on one instance after
changes: every capture is identical (functions, call sites, edges with all fields in order, file-to-file edges, the
NetworkX graph with weights, callers/callees maps, module/package maps, diagnostics; for RepoGraph every map, the
test-target and invocation maps, unresolved diagnostics, the degree-matched control graph and PageRank bit for bit).
The same comparison on the 1,000-file realistic corpus (outside the test suite) was identical as well.

## 6. Tests

| Suite | Tests | What it proves |
| :--- | ---: | :--- |
| `tests/test_stage2_resolvers.py` | 108 | Both optimised resolvers are identical to verbatim copies of the previous implementation (15 corpora × 4 function-graph configurations; 15 × class-to-test on/off; tracked and untracked; refits after changes). Dependency soundness: equal own inputs and equal consumed-key values imply equal edges, for every file of seeded random mutation sequences. Key values are functions of their ordered provider lists. All 12 key families are exercised. |
| `tests/test_stage2_bookkeeping.py` | 49 | BM25 updates equal `fit()` bit for bit including dictionary order (25 seeded sequences × 15 steps), full-fit fallbacks, counters; abstainer reference counts equal `fit()` (12 seeded sequences and the named scenarios). |
| `tests/test_stage2_mutations.py` | 40 | The 21-mutation catalogue (in-process refresh and warm restart, each compared with a fresh uncached build, then an unchanged restart that resolves nothing); uniqueness transitions in both directions for functions and class methods; body-only edits resolve one file; unconsumed provider changes do not expand the affected set; `max_files`, `persist_exclude` on/off, empty repository, repeated refreshes, discovery-order reversal, polyglot symbols; 3 seeded random sequences; the full 225-query corpus; a cross-process restart (same hash seed). |
| `tests/test_stage2_cache_safety.py` | 25 | Leases and eviction (subprocesses, kill), the pending purge (including a crash between publish and purge), migration (in place, idempotent, crash mid-migration, read-only, unverifiable), file ids, crash injection at the five writer points with provider changes, and two concurrent incremental writers plus two verifying readers while providers change. |
| Stage 1 cache suites | 134 | Unchanged, except artifact counts (nine kinds per file) and one message. |

**Results.**
- **Full suite, Python 3.11 (local, Windows), after the benchmarks:** 1,210 passed, 19 skipped, 1 failed. The failure
  was a test-timing issue: Windows releases a killed process's file locks asynchronously, and the test probed the
  exclusive lease immediately after the kill. The test now waits up to 15 s for the release (the product behaviour
  is unchanged: eviction skips a database whose lease is still held). The lease and eviction tests then passed in
  three consecutive runs, and the whole cache-safety file passed again (25 of 25). The 19 skips
  are the same as in Stage 1 (Tree-sitter and SCIP extras not installed locally, symlink creation and POSIX
  permission bits unavailable on this host).
- **Before the benchmarks** (same code): full suite 1,203 passed, 19 skipped (the 7 failures were the Space-bundle
  check before the bundle was synced); the bundle, Stage 1 and Stage 2 cache suites 357 passed, 2 skipped.
- **CI:** all 24 jobs passed on the pushed code (Python 3.10–3.12 on Linux; the index-cache suites, including every
  Stage 2 suite, on Linux, macOS and Windows; Tree-sitter, SCIP, MCP, wheel installs; the Stage 2 resolver tests also
  run in the Tree-sitter job). Tree-sitter-dependent tests are covered by CI only (Windows Application Control blocks
  the Tree-sitter library locally, as in Stage 1).

Every incrementally maintained engine is compared with a completely fresh **uncached** build of the same repository
state with the Stage 0 harness: documents, BM25 (arrays bit for bit, dictionaries in order, ordered postings),
semantic vocabulary and CSR arrays, RepoGraph and FunctionGraph (every node, edge, attribute, map and diagnostic, in
insertion order; PageRank bit for bit), the abstainer vocabulary, and retrieval for every ranker (ranked lists, scores
and component scores, explanations, abstention diagnostics, anchored change impact). Exact equality, no tolerances,
nothing sorted; the only exclusions are wall-clock fields. Every mutation test also asserts
`context_mismatches_outside_dependency_index == 0`: the dependency index never missed a change that the context
verification then caught.

## 7. Crash, concurrency and privacy results

- **Crash injection** (child process killed with `os._exit` after the building marker, after the first artifact
  batch, inside the publish before `COMMIT`, after the publish before garbage collection, inside garbage collection),
  now with provider changes in the change set: the database always reopens at the previous generation (same manifest
  digests, generation number and file ids) or the complete new one, verifies under `rebuild_policy="never"`, and is
  equivalent to a fresh build. A crash inside the migration transaction leaves version 1 intact; a crash between the
  publish and the purge leaves the purge marker, and the next writer completes it.
- **Concurrency:** two processes performing four incremental cached builds each while the test changes providers
  (second definitions, deleted definitions, added methods, a new winning module, a rename), with two processes
  verifying 20 loads each: every load verified, every build reported zero dependency-index misses, file ids stayed
  unique and below `next_file_id`, and the final state is equivalent to a fresh build. The Stage 1 suite (two
  writers × three publishes, three readers × 25 loads, lock waits and timeouts) passes unchanged.
- **Privacy:** the Stage 1 scanner (raw bytes, every zlib stream at every offset, every decoded payload of the
  database, WAL, SHM and all other cache files) finds no trace of an excluded file in all four Stage 2 artifact kinds,
  including after a purge, after a pending purge is completed, and after a crash before the purge. Excluded files
  never receive a file id, provider events, consumed keys, resolutions or reference counts.

## 8. Performance: Stage 1 versus Stage 2

`stage2_benchmark.py` uses the Stage 1 workload generator (same seed, same profiles) and runs every phase in a fresh
process, alternating which code (Stage 1 at `9cb4c46`, from a separate worktree, or Stage 2) goes first in each round.
Full data: `stage2_benchmark.json`. The machine (Windows 11, Python 3.12, SQLite 3.49.1, 15.5 GB RAM) was not idle and
had about 3–6 GB of RAM available; a phase whose committed memory exceeded the memory available when it started is
flagged as paging-suspected and not used as a clean comparison. Every round's final state was verified: a Stage 2
warm restart and a Stage 2 uncached build, each in its own process with `PYTHONHASHSEED=0`, produced the same
canonical digest of the complete index state and of retrieval for a query sample (**identical in 8 of 8 verified
rounds**: 3 × 1,000, 3 × 2,500, 2 × 10,000 reduced files).

### 8.1 Time to a ready engine (median of rounds, range in parentheses)

| Workload | Phase | Stage 1 | Stage 2 | Stage 1 / Stage 2 |
| :--- | :--- | ---: | ---: | ---: |
| 1,000 realistic files (3 rounds) | uncached build | 62.6 s (62.2–64.1) | 48.4 s (35.3–49.0) | 1.29× |
| | cold cached build | 67.7 s (54.3–68.6) | 57.1 s (41.2–57.8) | 1.19× |
| | warm restart, unchanged | 32.3 s (26.3–46.8) | 17.4 s (12.3–17.5) | **1.86×** |
| | restart after a one-file body edit | 42.2 s (20.9–59.8) | 17.5 s (11.7–17.8) | **2.42×** |
| 2,500 realistic files (3 rounds) | uncached build | 211.8 s (206.0–214.9) | 128.7 s (127.0–131.2) | 1.65× |
| | cold cached build | 228.4 s (227.4–238.2) | 150.5 s (148.1–162.6) | 1.52× |
| | warm restart, unchanged | 138.9 s (132.9–189.3) | 50.7 s (50.6–50.8) | **2.74×** |
| | restart after a one-file body edit | 141.8 s (135.1–163.4) | 50.5 s (50.3–51.8) | **2.81×** |
| 10,000 reduced files, clean round | uncached build | 66.5 s | 70.2 s | 0.95× |
| | cold cached build | 77.0 s | 62.1 s | 1.24× |
| | warm restart, unchanged | 42.7 s | 30.7 s | **1.39×** |
| | restart after a one-file body edit | 40.7 s | 30.2 s | **1.35×** |

The other 10,000-reduced round was paging-affected for the Stage 1 phases and the Stage 2 uncached build (3.0–3.5 GB
available against about 3.8–4.1 GB committed); its times (Stage 1 warm 93.0 s, Stage 2 warm 55.3 s) are in the JSON
and not used here. Warm restart versus uncached build within Stage 2: 2.8× at 1,000, 2.5× at 2,500 and 2.3× at
10,000 reduced files (Stage 1: 1.9×, 1.5×, 1.6× on the same rounds).

**Where the gain comes from.** At 2,500 files the warm-restart fit falls from 120.8 s (Stage 1) to 29.2 s (Stage 2):
the function graph from about 50 s of quadratic resolution (Stage 1 report §10; this benchmark does not split
Stage 1's fit) to 1.5 s (map building, context verification and replay;
no call resolved), RepoGraph to 1.5 s. The uncached build gains the same resolver speed-up (§5), which is why it is
faster too. The reduced profile has short files and few method-qualified calls, so its quadratic term was small to
begin with; there the uncached builds are equal within noise and the warm gain comes from reusing resolutions.

**What now dominates** (Stage 2 warm restart): the semantic refit (8.6 s of 17.4 s at 1,000 files; 21.6 s of 50.7 s
at 2,500; 15.1 s at 10,000 reduced), then loading and verifying every artifact (3.3 s, 14.3 s, 14.5 s). Both are global
or per-file work that Stage 2 does not address (semantic: Stage 3).

### 8.2 Work counters for representative updates (Stage 2 restart after each change)

| Change | 1,000 realistic: function-graph files / calls resolved | 2,500 realistic | 10,000 reduced |
| :--- | :--- | :--- | :--- |
| none (warm restart) | 0 / 0 of 51,729 | 0 / 0 of 124,761 | 0 / 0 of 78,582 |
| one-file body edit | 1 / 62 | 1 / 70 | 1 / 7 |
| one-file addition | 1 / 0 | 1 / 0 | 1 / 0 |
| deletion of a module | 0 / 0 (its keys had no consumers) | 359 / 20,048 | 820 / 9,295 |
| rename | 154 / 7,261 | 1 / 31 | 1 / 6 |
| provider change, many consumers (one definition → two) | 15 / 1,169 (14 affected through dependencies, 4 keys changed) | 20 / 1,735 | 27 / 301 |
| the reverse transition (two → one) | 14 / 1,169 | 19 / 1,735 | 26 / 301 |
| provider change, no consumers | 1 / 57 (0 affected through dependencies) | 1 / 36 | 1 / 11 |
| full discovery-order reversal | 432 / 21,304 (482 keys changed) | 1,101 / 52,921 | 3,172 / 29,676 |

RepoGraph re-resolved 0–10 files in every case except the order reversal (62 at 10,000 reduced). In every phase
`context_mismatches_outside_dependency_index` was 0. Wall time hardly moves with these counts (17.4–19.2 s at 1,000
files, 50.5–54.6 s at 2,500): after §5, resolving even 20,000 calls costs about a second, so the restart is dominated
by the global stages above. **Full PageRank and the other global graph stages ran on every restart** and are
reported as `recomputed_in_full`.

### 8.3 BM25 bookkeeping and in-process refresh

| Workload | BM25 in an in-process refresh after a one-file edit (partially incremental) | BM25 `fit()` at a warm restart |
| :--- | ---: | ---: |
| 1,000 realistic | 0.7 s (0.5–0.9) | 1.5 s (1.2–1.5) |
| 2,500 realistic | 1.9 s (1.5–3.3) | 3.9 s (3.7–4.1) |
| 10,000 reduced | 0.5 s (0.5–0.5) | 1.8 s (1.2–2.5) |

The bookkeeping beats the full refit by 2–3.6×, so it is kept for in-process refreshes. Most of its remaining cost is
the O(N) part (signature checks of every document, the global `avg_doc_len` and norms, rebuilding the ordered
dictionaries).

**The in-process `refresh()` as a whole is not faster than a fresh-process restart**: 20.6 s (15.9–21.4) against
17.4 s at 1,000 files; 58.9 s (37.8–76.6) against 50.7 s at 2,500; 32.7 s against 30.7 s at 10,000 reduced. Its fit
is no slower, but re-loading and verifying the whole generation inside a process that still holds the previous index
takes about twice as long (7.1 s against 3.5 s at 1,000 files; 21 s against 14 s at 2,500). Avoiding that reload for
artifacts already verified in memory is possible future work; Stage 2 keeps the full verified reload.

### 8.4 Memory, database and WAL

| Workload | Peak working set, uncached (S1 / S2) | Peak working set, warm (S1 / S2) | Database after cold build (S1 / S2) | Peak WAL, cold build (S1 / S2) |
| :--- | :--- | :--- | :--- | :--- |
| 1,000 realistic | 0.82 / 0.82 GB | 0.89 / 0.93 GB | 24.7 / 29.2 MB | 12.3 / 8.1 MB |
| 2,500 realistic | 1.91 / 1.91 GB | 2.06 / 2.17 GB | 61.9 / 72.9 MB | 12.6 / 8.4 MB |
| 10,000 reduced | 2.76 / 2.76 GB | 2.97 / 3.09 GB | 103.6 / 128.7 MB | 9.7 / 17.9 MB |

The Stage 2 database is 18–24% larger (the four new kinds; provider events are most of it), the warm working set 4–5%
larger (tracked resolutions and lookup indexes), and the WAL is truncated to 0 after every build. The writes per
publish grew too: persisting took 0.6 s against 0.3 s (1,000 files) and 3.0 s against 0.9 s (2,500 files).

### 8.5 Large corpora: 10,000 realistic and 30,000 reduced files (Stage 2 only, one round, paging-affected)

Both runs used the short mutation series. **Every phase was paging-affected** (8.4–10.1 GB committed against
5.4–8.4 GB available), so these timings are measurements under memory pressure, not clean comparisons. Stage 1 was
not re-run at these sizes: its function-graph resolution grows about N^2, and its recorded runs on this machine
(Stage 1 report §10, also paging-affected) took 2,607 s (uncached) and 2,825 s (warm restart) at 10,000 realistic
files and 1,155 s and 1,325 s at 30,000 reduced files. The work counters below do not depend on paging.

| Phase | 10,000 realistic: time | function-graph files / calls resolved | 30,000 reduced: time | function-graph files / calls resolved |
| :--- | ---: | :--- | ---: | :--- |
| uncached build | 313.1 s | (all) | 198.8 s | (all) |
| cold cached build | 457.3 s | 10,000 / 488,696 | 473.1 s | 30,000 / 237,214 |
| warm restart, unchanged | 171.8 s | 0 / 0 | 187.3 s | 0 / 0 |
| one-file body edit | 168.4 s | 1 / 71 | 195.9 s | 1 / 7 |
| one-file addition | 178.8 s | 1 / 0 | 197.6 s | 1 / 0 |
| provider change, many consumers | 163.9 s | 35 / 2,931 | 198.6 s | 18 / 284 |
| reverse transition | 160.7 s | 34 / 2,931 | 184.4 s | 17 / 284 |
| discovery-order reversal | 168.1 s | 4,460 / 208,317 | 177.2 s | 10,334 / 91,559 |

- In a warm restart the function graph took 7.7 s (10,000 realistic) and 6.7 s (30,000 reduced); the semantic refit
  71.4 s and 54.8 s, loading and verifying artifacts 47.4 s and 45.2 s, persisting 16.9 s and 36.8 s.
- **Writing is a large share at 30,000 files:** the cold build spent 259.6 s persisting (nine artifacts per file,
  270,000 rows, under paging), and every later publish 33–41 s, because the manifest and `file_artifacts` rows are
  replaced in full (design §18.8). A delta publish is future work.
- Databases: 288.5 MB (10,000 realistic; Stage 1: 244.9 MB) and 386.4 MB (30,000 reduced; Stage 1: 311.0 MB). Peak
  WAL during the cold build: 20.3 MB and 53.8 MB; 0 after every build.
- **The in-process refresh did not complete at either size.** The benchmark's memory watchdog stopped it at 13.0 GB
  committed (the limit was 12 GB): the previous engine stays in memory while the generation is re-loaded and the new
  index is built. A fresh-process restart needs about 9.4–10.1 GB at these sizes.
- **100,000 files:** not run. The in-memory index alone exceeded this machine at 100,000 reduced files in Stage 1
  (23.2 GB committed), and nothing in Stage 2 reduces that footprint. The size defaults remain provisional.

## 9. Schema migration, file ids and fingerprints

- **Version 1 → 2** (`schema.migrate`, called by `connection.open_writer`): one `BEGIN IMMEDIATE … COMMIT`. It
  re-reads `user_version` under the write lock (another process may have migrated), verifies the published version-1
  generation's manifest digest (an unverifiable database is not migrated and is treated as unusable), adds
  `manifest.file_id` with a unique index, assigns ids `1..n` in manifest-ordinal order, sets `meta.next_file_id`,
  recomputes the generation's manifest digest over the version-2 rows and sets `user_version = 2`. The file name is
  unchanged (minor, additive change, design §10.6).
- **Tested from an exact Stage 1 database** (the version-1 DDL verbatim, Stage 1 kinds and rows, the version-1
  digest): migrated in place, every Stage 1 artifact reused (`artifacts_reused = 5 × files`), graphs fall back to
  full resolution once (version 1 has no provider index), ids follow the ordinals, and the next restart resolves
  nothing; idempotent; a crash inside the migration transaction leaves a readable version 1 that the next writer
  migrates; a read-only client builds uncached and leaves the file byte-identical; a version-1 database that fails
  its digest is set aside and rebuilt.
- **File ids:** stable through edits and a reversed discovery order; deletion retires the id
  (`file_ids_retired`); re-adding the path or renaming a file allocates `next_file_id`; `persist_exclude`d files never
  get one and, when they stop being excluded, get new ids above every retired one; a lowered `next_file_id` or a
  changed id is rejected (manifest digest).
- **Fingerprints** (`fingerprints.py`): `ARTIFACT_VERSIONS` for the four new kinds; extractor fingerprints include
  `function-graph-resolver/2` or `repo-graph-resolver/2`, the resolution configuration (`min_confidence`,
  `enable_structural_edges`, `structural_parser`, `polyglot_symbols`) and the source digests of the resolver,
  dependency and codec modules; the index fingerprint adds the bookkeeping versions (`typed-keys/1`,
  `canonical-replay/1`, `bm25-partial/1`, `abstainer-refcounts/1`) and the new modules. A resolution artifact's key
  additionally binds the dependency context, recomputed from the current build before every reuse.

## 10. Known limitations

- **Global work remains.** The semantic index (Stage 3), PageRank, the degree-matched control graph, test-target maps,
  class-to-test linkage, both graphs' maps and the canonical replay are recomputed on every build. After §5 the
  semantic refit dominates warm restarts at every measured size.
- **Dependency-context verification costs about as much as indexed resolution.** Once the resolvers use lookup
  indexes, resolving a file is a few dictionary lookups per call; verifying a reused file's context is a lookup and a
  digest per consumed key. Dependency-scoped re-resolution therefore reduces resolution work in proportion to the
  change (see the counters in §8), but at the measured sizes it does not reduce wall time much compared with
  resolving everything with the indexes. It is kept because the brief requires dependency contexts to be recomputed
  from current inputs before reuse, and because it makes the reuse decision self-verifying.
- **In-process `refresh()` is slower and needs more memory than a fresh-process restart** (§8.3, §8.5): it
  re-loads and re-verifies the whole generation while the previous index is still in memory; at 10,000 realistic and
  30,000 reduced files it exceeded the benchmark's 12 GB memory limit.
- **Publishing grows with the file count:** the manifest and `file_artifacts` rows are replaced in full on every
  publish (33–41 s per build at 30,000 reduced files under paging; §8.5).
- **BM25 is partially incremental only within a process** (`refresh()` with an unchanged document set and order).
  Warm restarts refit BM25: its dictionary order follows the per-process hash seed (§4.1).
- **`persist_exclude` disables graph-contribution reuse** while any excluded file is indexed (the conservative
  option the brief allows); per-file artifacts of the other files are still reused.
- **Over-approximation.** Keys such as `fg.func:__init__` or common method names have long provider lists; any change
  to one of their providers re-resolves every consumer. This is correct but can enlarge the affected set.
- **Pre-existing hash-seed nondeterminism** (Stage 1 report §6) is unchanged: two uncached builds in processes with
  different `PYTHONHASHSEED` values already differ in some dictionary orders and explanation texts. Cross-process
  comparisons use the same seed; the cache adds no nondeterminism of its own (tested).
- **Downgrades.** A Stage 1 build of RepoNeedle that opens a version-2 cache reports an unsupported schema version and
  sets the database aside (Stage 1 behaviour); nothing is misread.
- **The purge** relies on `secure_delete`, incremental vacuum and WAL truncation; it is not a guarantee about the
  physical storage medium. Lease coordination covers RepoNeedle processes only (other programs opening the database
  do not take leases).
- **Tree-sitter and SCIP** configurations still take the uncached route (Stage 4).
- **Measurement gaps** are listed in §8.

## 11. Deferred work

- **Stage 3:** semantic document frequencies by delta, exact vocabulary maintenance with canonical first-seen order,
  and a vectorised IDF/norm recomputation, adopted only if bit-identical.
- **Stage 4:** Tree-sitter artifacts and availability changes, SCIP re-resolution on change, CLI/MCP cache flags and
  `cache info/clear/verify` commands, size limits across repositories.
- Persisting BM25 global state would need a hash-seed-independent dictionary order, which is a retrieval-state change
  requiring its own equivalence proof; it is not proposed.

## 12. Reproducing

```bash
python -m pytest tests/test_stage2_resolvers.py tests/test_stage2_bookkeeping.py tests/test_stage2_mutations.py \
    tests/test_stage2_cache_safety.py tests/test_stage1_cache_units.py tests/test_stage1_cache_lifecycle.py \
    tests/test_stage1_cache_corruption.py tests/test_stage1_cache_processes.py tests/test_stage1_persist_exclude.py
git worktree add ../stage1 9cb4c4614014dbdd4c85606d7fd3f91baf623762
D=reports/v2_completion/persistent_indexing
python $D/stage2_benchmark.py --stage1-root ../stage1 --files 1000 2500 --profile realistic --rounds 3 --verify \
    --out $D/stage2_benchmark.json
python $D/stage2_benchmark.py --stage1-root ../stage1 --files 10000 --profile reduced --rounds 2 --verify \
    --out $D/stage2_benchmark.json
python $D/stage2_benchmark.py --files 10000 --profile realistic --rounds 1 --series short --out $D/stage2_benchmark.json
python $D/stage2_benchmark.py --files 30000 --profile reduced --rounds 1 --series short --out $D/stage2_benchmark.json
```

## 13. Confirmations

- **No retrieval or ranking behaviour changed.** Ranking, score fusion, weights, default routing, CUD-Pack packing,
  token budgets and the default discovery order are untouched; the optimised resolvers produce identical graphs
  (verbatim previous implementation as oracle), and every cached or incrementally maintained engine equals a fresh
  uncached build exactly.
- **Default no-cache behaviour is unchanged** except for speed: without `index_cache` no database, lease or lock file
  is created, and the index state is identical to the previous release's.
- **What is incremental, and what is not:** graph call and import resolution, the dependency index and the abstainer
  vocabulary are incremental; BM25 is partially incremental (in-process `refresh()` only); the semantic index,
  PageRank, test-target maps, class-to-test linkage, the degree-matched control graph and the canonical replay are
  recomputed in full on every build and reported as such; fallbacks are labelled `fallback_full` with a reason.
- No raw source text is stored. No Stage 3 (semantic) or Stage 4 (optional components, CLI/MCP, cache commands)
  work was introduced. No new runtime dependency.
- Package version `1.2.0`. No release, tag, PyPI upload, Hugging Face upload or Render deployment. The bundled Space
  copy of the package was re-synchronised locally only. The PR is not merged.
