# V2 Stage 4: Large-Repository Scalability

**Branch:** `stage4/large-repo-scalability` (base `60fbfc0`, the merge of Stage 3, PR #27). **Package version:**
`1.2.0` in the source tree (already published; not changed, no new version). **Benchmark data:**
[`stage4_benchmark.json`](stage4_benchmark.json) and its generated summary [`stage4_benchmark.md`](stage4_benchmark.md),
produced by [`stage4_benchmark.py`](stage4_benchmark.py). Baseline `60fbfc072dcb35209aaea113ecd4162a9092a432`;
candidate `c5d9d22d27240c438a8ede22c67395dffaf03d69` (both clean trees, recorded in the JSON).

**Naming.** The persistent-indexing design (§15) used "Stage 4" for optional components and surfaces (Tree-sitter and
SCIP artifacts, CLI/MCP cache commands). The project's Stage 4 milestone is large-repository scalability (this
report). The optional-components work is unchanged in scope and still not started; the design document now lists it
separately (§20.6).

## 1. Summary

- **Finding.** On this machine (15.5 GB RAM, 3.4–6 GB available during the runs), **memory, not CPU, is what limits
  repository size.** In a built engine, the semantic per-document feature cache held **71% of the retained index
  memory at 10,000 reduced files (1,065 of 1,499 MB)** and 58% at 1,000 realistic files, because every
  (document, feature) pair kept its own string object: 15,300,236 string objects for 433,475 distinct features.
- **Change.** Feature strings are now shared (`sys.intern`) when a document's features are extracted and while each
  semantic artifact is decoded from the cache. Keys, counts, insertion order, persisted payloads, fingerprints and
  every index structure are unchanged; no cache artifact is invalidated.
- **Measured at 10,000 reduced files (three rounds, baseline re-measured in the same rounds):** retained index memory
  **1,499 → 854 MB (−43%)**; peak working set **−33% (uncached build), −32% (cold cached), −28% (warm restart)**;
  peak committed memory −0.66 GB in every phase. **The cost is time:** uncached build +10.6%, cold cached build
  +11.3%, warm restart **+21.7%** (cache loading 8.7 → 13.3 s), query latency median +9.5%. Exact four-way digest
  equivalence in all three rounds.
- **Larger workloads (one round each, no digest verification):** both completed every phase for both revisions.
  At 10,000 realistic files, retained memory −39% (4,348 → 2,635 MB) and peak working set −27% to −35%; the
  baseline's warm restart was paging-suspected (7.54 GB committed, 7.36 GB available) and the candidate's was not;
  time +4.8% uncached, +9.7% cold cached. At 30,000 reduced files, retained memory −44% (4,438 → 2,491 MB) and peak
  working set −33% to −34%, **but time +12.6% uncached and +27.9% cold cached, and the candidate's warm restart
  (112.4 s, cache loading 61.3 s) was slower than the baseline's paging-suspected one (73.4 s)**.
- **Assessment.** The change reliably cuts memory by about 40% at every size measured, with exact results, but its
  time cost grows with repository size and, in these runs, was not repaid by avoided paging. It is a measured
  trade-off for review, not an unqualified improvement; the report recommends a shared-feature cache codec as the
  structural fix (§11).
- **Benchmark infrastructure:** `stage4_benchmark.py` (deterministic dataset manifests, commit provenance, phase
  timings, retrieval latency, per-component retained memory, full statistics with visible exclusions, four-way digest
  verification), built on the Stage 1–3 harnesses.

## 2. Repository state

- Starting point: `origin/main` at `60fbfc0` (merge of PR #27, parents `0b27381` and `be86825`; tree identical to the
  reviewed `be86825`). Working tree clean.
- Commits: `430627f` (first interning version, tooling, tests, CI), `c5d9d22` (interning moved into the loader), and
  the documentation commit that adds this report.

## 3. Architecture findings: measured bottlenecks

Measured on the baseline (`60fbfc0`) at 10,000 reduced files (median of three rounds) unless stated otherwise.

| # | Bottleneck | Where | Evidence | Status |
| :--- | :--- | :--- | :--- | :--- |
| B1 | Retained memory: one string object per (document, feature) pair in the semantic feature cache | `reponeedle/core/semantic.py` (`_doc_feature_cache`, filled in `_fit_documents` on a miss) and the cache loader `reponeedle/core/index_cache/store.py` (`_load` decodes every semantic artifact) | 1,065 of 1,499 MB retained at 10,000 reduced (71%); 283 of 488 MB at 1,000 realistic (58%); 15.3 M string objects for 433 k distinct features | **Addressed** (§4) |
| B2 | Warm restart: the whole generation is decoded and verified eagerly | `store.load_generation` / `store._load` | 8.7 s of a 21.5 s warm restart (40%) | Not addressed; candidate for lazy or batched loading |
| B3 | Cold cached build: persisting | `session._persist`, `CacheWriter.write_artifacts` and `publish` (manifest and `file_artifacts` replaced in full) | 14.7 s of a 51.0 s cold cached build | Not addressed (delta publish; design §18.8) |
| B4 | Uncached and cold builds: semantic feature extraction | `semantic_features.extract_features` / `count_features` (per-document Python n-gram loop) | about 13 s of the 16.7 s semantic phase of an uncached build (the fit itself is about 3.3 s) | Not addressed: the module defines the semantic artifact fingerprint, so any change re-extracts every artifact |
| B5 | Warm restart: every file is read and hashed | `session._scan` → `engine._scan_repository` | 3.0 s per warm restart | Not addressed (lazy content, design §16.2) |
| B6 | Retained memory, secondary | `abstention.py` (`_doc_vocab_cache`, per-document token sets), `lexical.py` (`_doc_term_cache`, `inverted_index` postings of tuples), `function_graph.py` | 110 MB, 99 + 106 MB and 77 MB at 10,000 reduced | Not addressed; the same per-document string duplication applies, but these modules are fingerprinted |
| B7 | Global fits on every restart | BM25 refit (1.1 s), semantic fit (3.3 s), graph replay and PageRank (about 1.5 s) | `CachedAssembly.fit_all` | Unchanged (by design, Stages 2–3) |

Retrieval itself is not a bottleneck at these sizes: the median latency of 25 fixed queries on a warm 10,000-file
engine was 37 ms (baseline).

## 4. Implementation

**`reponeedle/core/semantic.py`** — `shared_feature_counts(counts)` returns the same counts with every key passed
through `sys.intern` (`dict(zip(map(sys.intern, counts), counts.values()))`: same keys, values and insertion
order). `SubwordSemanticIndex.fit()` applies it to every document whose features it extracts.

**`reponeedle/core/index_cache/store.py`** — `_load` applies it to each semantic artifact as it is decoded. The whole
generation is decoded at once, so sharing at decode time is what lowers the warm-restart peak.

**Why there, and not elsewhere.**
- `semantic_features.py` and `codecs.py` are part of the `semantic` artifact's extractor fingerprint (codecs: of every
  kind's). Changing either would make every existing cache re-extract its artifacts. `semantic.py` and `store.py` are
  not part of any extractor fingerprint; all nine extractor fingerprints are unchanged from Stage 3.
- A first version (`430627f`) interned at cache-seeding time instead. Measured in one preliminary round at 10,000
  reduced files (not part of the results), it reduced retained memory but barely the warm-restart peak (2.37 → 2.30
  GB), because the loader had already decoded every artifact with its own strings. `c5d9d22` moved the sharing into
  the loader; `session.py` is unchanged from Stage 3.
- `sys.intern` rather than a per-index table: on the interpreters tested here (CPython 3.11.9 and 3.12.10) interned
  strings are mortal (checked: an interned string's reference count is ordinary), so features of deleted documents
  are released in a long-running process that refreshes. Some early CPython 3.12 releases made interned strings
  immortal; on those, every distinct feature ever seen stays allocated for the life of the process (bounded by the
  number of distinct features, about 25 MB at 10,000 reduced files). This was not tested on those releases.

**What is not changed:** cache schema (version 2), codecs, payloads, artifact keys, fingerprints, retrieval, ranking,
fusion, routing, packing, token budgets, discovery order, public API, dependencies.

## 5. Benchmark infrastructure

`reports/v2_completion/persistent_indexing/stage4_benchmark.py` extends the Stage 1–3 tooling instead of duplicating
it: the seeded Stage 1 generator (`stage1_benchmark.generate`, seed 7), the Stage 2 child (memory watchdog, WAL
watcher, canonical digest) and the Stage 3 additions (heartbeat, keep-awake request, semantic-fit timer, power-event
check). It adds:

- **Dataset manifest** per workload: dataset id, generator version, seed, profile, file count, language distribution,
  size statistics (total, mean, min, p10, p50, p90, p99, max), directory statistics, test files, import lines, the
  generator configuration, generation time and a **SHA-256 over every file's path and content digest**.
- **Provenance**: both revisions' commit SHAs, whether their trees were clean, and the package version; environment
  (OS, Python, NumPy, SciPy, NetworkX, pydantic, pathspec, SQLite, CPU, logical CPUs, total and available RAM) and the
  command line with path arguments reduced to their last component (the committed JSON was produced before that
  reduction was added and was redacted the same way, marked `argv_redacted_after_run`).
- **Phases** per round and revision, each in a fresh process: uncached build, cold cached build, warm restart; the
  engine's own phase timings (scan, load, fit and its sub-stages, persist); the semantic-fit wall time; peak working
  set, peak committed memory, memory available at start, peak WAL; heartbeat gap; **retrieval latency** of 25 fixed
  queries on the warm engine.
- **Per-component retained memory** of an uncached build (deep object sizes, each object counted once), plus the
  number of semantic pairs, distinct features and distinct key objects.
- **Statistics**: median, minimum, maximum, standard deviation and n for every metric; per-round ratios; excluded
  (paging- or suspension-suspected) and failed phases listed, never dropped from the raw data.
- **Verification** (`--verify`): each round, the warm restart and the uncached build of both revisions must give one
  digest of the complete index state and of retrieval under `PYTHONHASHSEED=0`.
- A Markdown summary generated from the JSON.

Reproduction:

```
git worktree add <dir> 60fbfc072dcb35209aaea113ecd4162a9092a432
python reports/v2_completion/persistent_indexing/stage4_benchmark.py --baseline-root <dir> \
    --files 10000 --profile reduced --rounds 3 --verify --component-memory \
    --out reports/v2_completion/persistent_indexing/stage4_benchmark.json
python reports/v2_completion/persistent_indexing/stage4_benchmark.py --baseline-root <dir> \
    --files 10000 --profile realistic --rounds 1 --component-memory --out <same file>
python reports/v2_completion/persistent_indexing/stage4_benchmark.py --baseline-root <dir> \
    --files 30000 --profile reduced --rounds 1 --component-memory --out <same file>
```

Generated repositories are written to a temporary directory and deleted; only manifests are kept.

## 6. Results

Every phase ran in a fresh process. Baseline `60fbfc0` and candidate `c5d9d22` ran in the same rounds, alternating
which went first. The machine was asked to stay awake; no sleep or Modern Standby event was logged during any
workload and no phase was suspended (threshold 5 s). The largest heartbeat gaps, 4.9 s and 4.8 s, were in the
baseline's memory-probe children at 30,000 reduced and 10,000 realistic files: a long pure-Python object traversal that
holds the interpreter lock, not a suspension; that probe reports object sizes, not times. The largest gap in a timed
phase was 2.2 s. Phases whose committed memory exceeded the memory available when they started are
`paging_suspected` and excluded from the comparison (listed). A preliminary round of the first implementation
(`430627f`, §4) is not part of these results.

### 6.1 10,000 reduced files (three rounds, with four-way digest verification)

Dataset `stage1-generator/reduced/10000/seed-7`: 10000 files, 14.7 MB (p50 1140 B, p90 2984 B, max 23922 B), 4000 directories, languages {'.go': 663, '.java': 466, '.json': 776, '.md': 1578, '.py': 4478, '.rs': 513, '.ts': 1526}, manifest SHA-256 `4d7140fe8cdafc4785fa7d2f0733e7b6c1a87e22a4811e15d9cfe72d3577c1d6`. Rounds: 3. Sleep/standby events: none.

| Phase | Metric | Baseline | Candidate | Change |
| :--- | :--- | ---: | ---: | ---: |
| uncached build | time to ready engine | 35.6 s (35.3–35.8, sd 0.3) | 39.4 s (38.7–40.8, sd 1.1) | +10.6% |
| uncached build | semantic phase | 16.68 s (16.66–16.78, sd 0.06) | 20.60 s (20.11–21.61, sd 0.76) | +23.5% |
| uncached build | peak working set | 2.05 GB (2.05–2.05, sd 0.00) | 1.38 GB (1.38–1.38, sd 0.00) | -32.6% |
| uncached build | peak committed | 3.10 GB (3.10–3.10, sd 0.00) | 2.44 GB (2.43–2.44, sd 0.00) | -21.5% |
| cold cached build | time to ready engine | 51.0 s (49.9–51.3, sd 0.7) | 56.7 s (56.5–56.7, sd 0.1) | +11.3% |
| cold cached build | semantic phase | 16.86 s (16.27–16.92, sd 0.36) | 20.59 s (20.44–20.63, sd 0.10) | +22.2% |
| cold cached build | peak working set | 2.08 GB (2.08–2.08, sd 0.00) | 1.41 GB (1.41–1.41, sd 0.00) | -32.2% |
| cold cached build | peak committed | 3.14 GB (3.14–3.14, sd 0.00) | 2.47 GB (2.47–2.47, sd 0.00) | -21.4% |
| warm restart | time to ready engine | 21.5 s (21.4–21.8, sd 0.2) | 26.2 s (25.9–26.4, sd 0.3) | +21.7% |
| warm restart | semantic phase | 3.30 s (3.25–3.33, sd 0.04) | 2.92 s (2.89–2.94, sd 0.03) | -11.6% |
| warm restart | peak working set | 2.37 GB (2.37–2.37, sd 0.00) | 1.71 GB (1.71–1.71, sd 0.00) | -27.7% |
| warm restart | peak committed | 3.43 GB (3.42–3.43, sd 0.00) | 2.77 GB (2.77–2.77, sd 0.00) | -19.2% |

| Component (retained, uncached build) | Baseline MB | Candidate MB | Change |
| :--- | ---: | ---: | ---: |
| documents raw text | 15.2 | 15.2 | +0.0% |
| documents metadata | 9.6 | 9.6 | +0.0% |
| semantic feature cache | 1064.9 | 421.8 | -60.4% |
| semantic vocabulary idf matrix | 0.9 | 0.9 | +0.0% |
| lexical term cache | 98.6 | 98.6 | +0.0% |
| lexical index rest | 106.1 | 106.1 | -0.0% |
| abstainer | 109.6 | 109.6 | +0.0% |
| function graph | 76.9 | 75.2 | -2.2% |
| repo graph | 16.5 | 16.5 | -0.0% |
| engine rest | 0.3 | 0.3 | -0.0% |
| **total** | **1498.7** | **853.9** | **-43.0%** |

Query latency (median of 25 fixed queries per round): baseline 39.7 / 37.4 / 36.9 ms, candidate 41.3 / 40.9 / 40.1 ms. Engine phases (median s): warm restart load 8.7 → 13.3, scan 3.0 → 3.0, fit 6.0 → 6.1, persist 3.4 → 3.4; cold cached build scan 5.0 → 5.1, fit 31.1 → 35.3, persist 14.7 → 16.2.

### 6.2 10,000 realistic files (one round)

Dataset `stage1-generator/realistic/10000/seed-7`: 10000 files, 85.3 MB (p50 6615 B, p90 17844 B, max 141016 B), 4000 directories, languages {'.go': 738, '.java': 468, '.json': 786, '.md': 1516, '.py': 4482, '.rs': 507, '.ts': 1503}, manifest SHA-256 `32b892595492e42c45924f9c513ca00e4731c67e789987377607a4ec8275b41a`. Rounds: 1. Sleep/standby events: none.

| Phase | Metric | Baseline | Candidate | Change |
| :--- | :--- | ---: | ---: | ---: |
| uncached build | time to ready engine | 137.3 s | 143.9 s | +4.8% |
| uncached build | semantic phase | 64.55 s | 74.98 s | +16.2% |
| uncached build | peak working set | 5.48 GB | 3.67 GB | -33.0% |
| uncached build | peak committed | 6.54 GB | 4.73 GB | -27.6% |
| cold cached build | time to ready engine | 159.3 s | 174.8 s | +9.7% |
| cold cached build | semantic phase | 64.16 s | 76.22 s | +18.8% |
| cold cached build | peak working set | 5.62 GB | 3.66 GB | -34.9% |
| cold cached build | peak committed | 6.69 GB | 4.89 GB | -26.9% |
| warm restart | time to ready engine | excluded (48.6 s, paging-suspected) | 57.4 s | – |
| warm restart | semantic phase | excluded (10.45 s, paging-suspected) | 8.17 s | – |
| warm restart | peak working set | excluded (6.47 GB, paging-suspected) | 4.73 GB | – |
| warm restart | peak committed | excluded (7.54 GB, paging-suspected) | 5.79 GB | – |

| Component (retained, uncached build) | Baseline MB | Candidate MB | Change |
| :--- | ---: | ---: | ---: |
| documents raw text | 85.7 | 85.7 | +0.0% |
| documents metadata | 25.0 | 25.0 | +0.0% |
| semantic feature cache | 2801.0 | 1093.7 | -61.0% |
| semantic vocabulary idf matrix | 0.9 | 0.9 | +0.0% |
| lexical term cache | 366.7 | 366.7 | +0.0% |
| lexical index rest | 413.7 | 413.7 | -0.0% |
| abstainer | 218.6 | 218.6 | +0.0% |
| function graph | 388.6 | 382.8 | -1.5% |
| repo graph | 47.7 | 47.7 | -0.0% |
| engine rest | 0.3 | 0.3 | -0.0% |
| **total** | **4348.2** | **2635.2** | **-39.4%** |

The baseline's warm restart committed 7.54 GB with 7.36 GB available and is excluded (paging-suspected; its 48.6 s is in the raw data); the candidate's committed 5.79 GB with 6.97 GB available. Engine phases (s): warm restart load 21.2 → 32.3, fit 20.1 → 17.6; cold cached fit 124.0 → 138.3, persist 23.3 → 24.6. Query latency median 60.4 → 60.0 ms.

### 6.3 30,000 reduced files (one round)

Dataset `stage1-generator/reduced/30000/seed-7`: 30000 files, 44.0 MB (p50 1140 B, p90 3002 B, max 33463 B), 4000 directories, languages {'.go': 2104, '.java': 1461, '.json': 2311, '.md': 4576, '.py': 13540, '.rs': 1505, '.ts': 4503}, manifest SHA-256 `9498fea5849c70bd31cde5e0025fb2edc82e47d9cb24546d7cebab6791326d94`. Rounds: 1. Sleep/standby events: none.

| Phase | Metric | Baseline | Candidate | Change |
| :--- | :--- | ---: | ---: | ---: |
| uncached build | time to ready engine | 112.4 s | 126.5 s | +12.6% |
| uncached build | semantic phase | 55.69 s | 71.06 s | +27.6% |
| uncached build | peak working set | 5.90 GB | 3.87 GB | -34.4% |
| uncached build | peak committed | 6.96 GB | 4.93 GB | -29.2% |
| cold cached build | time to ready engine | 266.0 s | 340.1 s | +27.9% |
| cold cached build | semantic phase | 55.02 s | 70.54 s | +28.2% |
| cold cached build | peak working set | 5.92 GB | 3.98 GB | -32.8% |
| cold cached build | peak committed | 7.09 GB | 5.06 GB | -28.7% |
| warm restart | time to ready engine | excluded (73.4 s, paging-suspected) | 112.4 s | – |
| warm restart | semantic phase | excluded (11.54 s, paging-suspected) | 10.86 s | – |
| warm restart | peak working set | excluded (6.85 GB, paging-suspected) | 4.85 GB | – |
| warm restart | peak committed | excluded (7.93 GB, paging-suspected) | 5.92 GB | – |

| Component (retained, uncached build) | Baseline MB | Candidate MB | Change |
| :--- | ---: | ---: | ---: |
| documents raw text | 45.4 | 45.4 | +0.0% |
| documents metadata | 28.8 | 28.8 | +0.0% |
| semantic feature cache | 3184.0 | 1240.9 | -61.0% |
| semantic vocabulary idf matrix | 1.0 | 1.0 | +0.0% |
| lexical term cache | 294.4 | 294.4 | +0.0% |
| lexical index rest | 288.5 | 288.5 | -0.0% |
| abstainer | 319.8 | 319.8 | +0.0% |
| function graph | 226.4 | 222.3 | -1.8% |
| repo graph | 48.9 | 48.9 | -0.0% |
| engine rest | 1.2 | 1.2 | -0.0% |
| **total** | **4438.3** | **2491.1** | **-43.9%** |

The baseline's warm restart committed 7.93 GB with 7.67 GB available and is excluded (paging-suspected; 73.4 s in the raw data). The candidate's warm restart committed 5.92 GB with 6.28 GB available: not flagged, but close enough that some paging cannot be ruled out. Engine phases (s): warm restart load 27.3 → 61.3, persist 15.2 → 19.4; cold cached fit 99.3 → 115.1, persist 152.5 → 210.9 (interning does not change what is persisted; the persist difference is unexplained in one round). Query latency median 110.5 → 134.5 ms.

## 7. Correctness

- **Digest equivalence at scale.** In all three 10,000-reduced rounds, four builds produced one digest of the complete
  index state and of retrieval for the fixed query sample (`PYTHONHASHSEED=0`): baseline warm restart, baseline
  uncached build, candidate warm restart, candidate uncached build. The digest is `55b48fb2…` in every round. The
  10,000-realistic and 30,000-reduced runs were single rounds without digest verification (§9).
- **Tests** (`tests/test_v2_stage4_scalability.py`, 12 tests): shared counts keep keys, values and order; after
  extraction and after a cached restart, each distinct feature is exactly one interned object; the loader shares
  strings as it decodes and its output equals the engine's cache; `refresh()` keeps them shared; persisted semantic
  payloads are byte-identical to the encoding of the Stage 2 reference's extraction; every structure and score array
  equals the verbatim Stage 2 reference and a fresh uncached build. The benchmark tooling is covered by tests of
  manifest determinism, statistics and exclusions, commit provenance, a platform without `SC_AVPHYS_PAGES` (macOS;
  found by CI and fixed in `5b87eb9`), and an end-to-end run that checks the output schema, the four-way digest and
  that key objects equal distinct features.
- **Existing suites**: the Stage 0–3 cache, semantic, equivalence and bundle suites pass unchanged (§10).
- **Fingerprints**: no change to `semantic_features.py`, `codecs.py` or any module in an extractor fingerprint; all nine
  extractor fingerprints are those of Stage 3.

## 8. Memory analysis

Three different measurements are reported; they are not interchangeable:
- **Retained component memory** (§6 tables): deep object sizes of the structures a built engine keeps, each object
  counted once in the listed order (so a string shared by two components is attributed to the first; the small
  function-graph differences come from this, not from a change). It excludes interpreter overhead, freed memory and
  allocator fragmentation.
- **Peak working set**: the process's largest resident memory during the phase (operating-system counter).
- **Peak committed memory**: the process's largest private committed memory; compared with the physical memory
  available when the phase started to flag paging.

The semantic feature cache was the largest retained component at every size measured and shrank by 60–61%; it is
still the largest after the change (422 MB at 10,000 reduced, 1,094 MB at 10,000 realistic), because each document
keeps its own dict of features and counts. The next components are the lexical term cache and index (205 MB and
780 MB), the abstainer (110 and 219 MB) and the function graph (77 and 389 MB). The raw text of the files is small in
comparison (15 and 86 MB). The cache database is unchanged in size (122.8 MB at 10,000 reduced, 275.1 MB at 10,000
realistic) and the WAL is truncated after every build.

## 9. Limitations

- **Time cost.** The change trades time for memory (§6). On a machine with ample free memory it makes every build
  slower; it pays off only where the baseline would page. The warm-restart cost (+21.7% at 10,000 reduced) comes from
  interning while decoding: about 0.3 µs per (document, feature) pair.
- **Query latency** rose 9.5% (median) at 10,000 reduced files, consistently across rounds; the cause was not
  established (nothing in the query path reads the feature cache). At 10,000 realistic files the medians were equal
  (60.4 and 60.0 ms, one round); at 30,000 reduced files the candidate was 22% slower (110.5 → 134.5 ms, one round).
- **The time cost grows with size.** Cold cached build +11.3% at 10,000 reduced files, +9.7% at 10,000 realistic and
  +27.9% at 30,000 reduced files; warm-restart cache loading 1.5× at 10,000 files and 2.2× at 30,000 reduced files.
- **Single rounds** at 10,000 realistic and 30,000 reduced files, without digest verification; their timings carry
  more uncertainty, and paging-suspected phases are excluded and listed.
- **Paging-dependent conclusions.** Whether a phase pages depends on the memory other programs were using at the time
  (2–7.5 GB was available during these runs).
- **CPython version.** Interned strings were checked to be mortal on CPython 3.11.9 and 3.12.10; some early 3.12
  releases made them immortal (§4).
- **Not measured:** 30,000 realistic files, 100,000 files, repeated rounds at 10,000 realistic and 30,000 reduced files,
  `refresh()` and mutation series at these sizes, other machines and operating systems.
- **Per-component memory at 1,000 files** (§3, B1) comes from the exploratory probe used to find the bottleneck, not
  from the benchmark JSON.

## 10. Tests and checks

Commands and results are listed in the pull request description (local runs on Windows, Python 3.12; CI on the
final commit).

## 11. Recommended next experiments

1. **Shared-feature codec (highest value).** Store each distinct semantic feature once per generation and per-document
   counts as integer ids: decoding would create no per-pair strings at all (removing both the remaining duplicate
   memory and the interning cost) and the payloads would shrink. Requires a codec version, a fingerprint change and a
   migration path; measure decode time and database size first.
2. **Lazy or streamed generation loading** (`store._load`, B2): decode artifacts kind by kind as the build consumes
   them instead of the whole generation at once, to cut the warm-restart peak and time further.
3. **The same sharing for lexical terms and abstainer tokens** (B6), done in the loader and at fit time without
   changing fingerprinted modules, then measured the same way.
4. **Repeated rounds at 10,000 realistic and 30,000 reduced files** on a machine with enough free memory for the
   baseline, to separate the code's cost from paging.
5. **Delta publishing** (B3) for cold builds and large refreshes.
