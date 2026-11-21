# V2 Stage 4.1: shared semantic feature dictionary

**Scope:** replace Stage 4's `sys.intern` sharing (PR #28) with a representation that keeps the memory reduction without its time cost, with exact retrieval and no cache invalidation.
**Branch:** `stage4.1/shared-feature-dictionary`, stacked on PR #28 (head `643fa22`). Draft PR #29.
**Machine:** Windows 11, Python 3.12.10, numpy 2.5.2, SciPy 1.18.1, 18 logical CPUs, 16 GB RAM. One machine; nothing here is extrapolated to others.

## 1. Summary

- **Root cause of the Stage 4 time cost** (measured, §3): `sys.intern` itself is not the problem. The cost is one hash-table probe per (document, feature) pair plus a second per-document dict built for every document. That adds +4.9 s when features are extracted and +5.1 s when the cache is decoded, at 10,000 reduced files (15.3 M pairs, 433 k distinct features). A private canonical dict instead of the global intern table costs the same. The garbage collector plays no part: about 120 k tracked objects and a 0.04 s full collection in every variant.
- **Built (§5):** each document's feature counts are int32 ids into one append-only, per-index `FeaturePool` (one string per distinct feature) plus counts, behind a read-only `Mapping` with the dict's exact keys, values and order. `fit()` derives the first-seen order, document frequencies and matrix columns from the ids with array operations; the per-pair Python pass is gone.
- **Unchanged:** persisted payloads, codecs, schema, the nine extractor fingerprints, every index structure and retrieval. Caches written by Stage 3 and Stage 4 are reused with no re-extraction, and caches written by Stage 4.1 are reused by Stage 3 and Stage 4 (§9).
- **End to end** (§6; 10,000 reduced files; 3 rounds × 3 revisions; every phase on mains power; nothing excluded; one identical digest across all 18 builds). Stage 4.1 against Stage 3, with the Stage 4 comparison in brackets:
  - uncached build: 35.5 s vs 34.9 s, +1.8% (Stage 4: −11%);
  - cold cached build: 47.5 s vs 50.9 s, −6.7% (−17%);
  - warm restart: 21.9 s vs 21.8 s, +0.8% (−18%);
  - median query latency: 36.6 ms vs 37.0 ms (−10%). Paired per query, Stage 4.1 is 1.4% faster than Stage 3 and Stage 4 is 13.5% slower than Stage 4.1.
- **Memory** (§7):
  - retained index memory: 1,506 MB (Stage 3), 861 MB (Stage 4), **613 MB** (−59% against Stage 3, −29% against Stage 4);
  - peak working set: 2.05 / 1.38 / **1.09 GB** uncached, and 2.37 / 1.71 / **1.43 GB** on a warm restart.
- **Verdict: PERFORMANCE RECOVERY SUCCESSFUL at 10,000 reduced files** (§13). Stage 4's memory reduction is kept and deepened, and its time and latency cost is removed. 10,000 realistic and 30,000 reduced files were not measured for Stage 4.1.

## 2. Current architecture (Stage 4, `643fa22`)

- **Extraction:** `semantic_features.count_features(doc)` returns a dict of feature string → count in first-occurrence order. This module, `codecs.py`, the tokenizer and the signature module define the `semantic` artifact's extractor fingerprint.
- **Stage 4 sharing:** `semantic.shared_feature_counts` rebuilds that dict through `sys.intern`, at extraction and while `store._load` decodes each artifact. The decode happens because the loader decodes the whole generation at once.
- **Fit:** one Python pass over every (document, feature) pair, `first_ticket.setdefault(feature, ticket)`, gives the first-seen order. Array operations do the rest.
- **Persistence:** one `semantic-counts-json/1` artifact per document, `{"f": [features], "c": [counts]}` zlib-compressed. It is content-addressed (the key covers the kind, extractor fingerprint, path, text and metadata digests and input signature) and is reused across generations with `INSERT OR IGNORE`.
- **Retrieval:** `score()` uses only the vocabulary, IDF and normalised CSR matrix. The per-document cache is read only by `fit()` and when artifacts are persisted.

## 3. Phase A: where the time goes (profiling)

**Method.** `stage4_1_profile.py` ran each representation in its own fresh process. That isolation matters because the intern table is process-global. Every run used the same 10,000 reduced-file corpus as Stage 4 (manifest SHA-256 `4d7140fe…`, identical to `stage4_benchmark.json`) and the `643fa22` fit, codec and loader. Each run measures:

- extraction and representation building;
- a first fit;
- encoding every artifact with the unchanged codec;
- decoding all of them as a restarted process would;
- a refit on the decoded state;
- semantic scoring of the 25-query sample, five times;
- a full GC collection;
- retained size of the representation: containers, each distinct key object once, and any pool.

Every variant produced the same index digest after both fits (`e0f80521…`). Raw data: `stage4_1_profile.json`.

| Variant (10,000 reduced, round 1) | Retained representation | Conversion at extraction | Fit | Encode | Decode + conversion | Refit after decode | Semantic score median / p90 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `plain`: Stage 3 dicts | 1,063.2 MB | 0 | 5.87 s | 4.83 s | 5.62 s | 5.20 s | 22.1 / 27.5 ms |
| `intern`: Stage 4 | 422.5 MB | 4.90 s | 4.40 s | 4.29 s | 10.74 s | 4.00 s | 22.0 / 26.8 ms |
| `pool`: private canonical dict | 437.2 MB | 3.86 s | 4.56 s | 4.48 s | 10.49 s | 4.72 s | 22.8 / 30.3 ms |
| `ids`: int32 ids + pool | **159.1 MB** | 2.74 s | **2.02 s** | 6.79 s¹ | 8.41 s | **1.75 s** | 22.7 / 27.7 ms |
| `ids_bin`: ids + binary payload² | 159.1 MB | 3.21 s | 1.88 s | 2.38 s | **1.24 s** (r2: 1.13 s) | 1.65 s (r2: 1.73 s) | 23.0 / 27.7 ms |

¹ The prototype re-built a dict per document to encode it. The production `FeatureCounts` is encoded directly, and its cost is in the benchmark's `persist_ms`.
² This is the upper bound for a persisted integer-id format: a binary id array per document plus one dictionary. It is a prototype only, not built.

Extraction itself ranged from 17.4 to 19.3 s for identical code, which gives this machine's run-to-run noise (about ±5%). Round 2 was stopped after its first variant so that test runs would not overlap it. Only `ids_bin` has two rounds.

**Findings.**

1. **The time penalty is per-pair work, not interning as such.** Interning adds 4.9 s at extraction and 5.1 s at decode, close to the regressions Stage 4 measured end to end (+4.8 s uncached, +4.6 s cache loading). That is about 320 ns per pair: a probe of a 433,000-entry table that misses the CPU caches, a string comparison, and building a second dict per document. A private dict (`pool`) costs the same, so the global intern table is not the cause.
2. **The garbage collector is not involved.** Every variant had about 117,000 to 127,000 GC-tracked objects and a 0.04 to 0.05 s full collection, because dicts of strings and ints are untracked.
3. **Fit time is dominated by the per-pair first-seen pass.** The `feature_counting` sub-stage took 3.5 s of a 5.2 s plain refit. Shared strings speed it up slightly: identity comparison beats a memcmp. Integer ids remove it, since the first-seen order comes from one boolean mask per document.
4. **Semantic scoring does not depend on the representation:** medians were 22.0 to 23.0 ms in all variants. The per-document cache is not read at query time.
5. **With the existing persisted format, decode cost is bounded by the JSON decoder.** Creating 15.3 million strings and then hashing them once costs about 5.6 s whatever is built from them. Only a different persisted format (`ids_bin`, 1.2 s) avoids it.

## 4. Alternatives and the choice

| Design | Retained repr. (10k reduced) | Extraction + fit | Decode + refit (warm) | Cache compatibility | Complexity |
| :--- | ---: | ---: | ---: | :--- | :--- |
| Stage 3 dicts | 1,063 MB | 5.9 s | 10.8 s | n/a (published format) | — |
| Stage 4 `sys.intern` | 423 MB | 9.3 s | 14.7 s | unchanged format | small |
| private string pool | 437 MB | 8.4 s | 15.2 s | unchanged format | small; no gain over intern |
| **integer ids in memory, unchanged format (built)** | **159 MB** | **4.8 s** | **10.2 s** | **unchanged format** | moderate, contained in `semantic.py` and two lines of `store.py` |
| integer ids, persisted binary format | 159 MB | 5.1 s | 2.9 s | new codec; generation-level dictionary | high (see below) |

All figures are from the Phase A profile: one round, semantic work only, not whole-engine time. The end-to-end comparison (§6) could not be completed in this sprint.

**Why not a persisted integer-id format now?** It is the only design that removes the JSON decode cost (about 7 s of a 10,000-file warm restart). But per-document artifacts are content-addressed, immutable and shared across generations, so ids that refer to a generation-level dictionary would make an artifact valid only together with that dictionary. Keeping reuse would need an append-only dictionary whose identity enters the artifact key (or input signature). It would also need:

- concurrent writers that never assign the same id to different strings, or the reverse;
- compaction that rewrites every artifact;
- a codec version, with a fallback reader for existing caches;
- interruption tests for the migration.

That is a change to the storage protocol, not a representation change. The evidence justifies it only after the in-memory change, and it needs its own design review. It is listed as the next step with its measured upper bound (§11).

## 5. What was built

**Source files changed:**

- `reponeedle/core/semantic.py`:
  - `FeaturePool`: a dict subclass, feature → id, with `strings` holding one object per distinct feature. It is append-only, and `ids()` returns int32 arrays.
  - `FeatureCounts`: a slotted, read-only `Mapping` holding `pool`, `ids` (int32) and `counts` (int32, or int64 if any count exceeds 2³¹−1). `__iter__`, `keys()`, `values()` and `items()` follow the document's first-occurrence order. Equality is the dict's (order-insensitive). `__getitem__` is a linear search, and no engine path uses it.
  - `fit()`, step 1: cache entries end up in the index's pool. An empty pool adopts the loader's pool. Any other pool is translated once per pool by a single id table, and plain mappings are converted.
  - `fit()`, step 2: first-seen order comes from a per-document boolean mask, `ids[~seen[ids]]`, which is exact because a document's ids are distinct. Document frequencies are a `bincount` over dense ids, and matrix columns are a gather. Steps 3 to 5 (vocabulary `lexsort`, IDF, CSR values, normalisation) are unchanged from Stage 3.
  - Compaction: once the pool exceeds `2 × max(live features, last compacted size) + 65,536`, the index builds a new pool holding only the features some cache entry refers to, and remaps every entry. Pools are append-only, so whatever else still refers to the old pool, such as a loaded generation, stays valid.
  - `shared_feature_counts` (Stage 4) is removed.
- `reponeedle/core/index_cache/store.py`: `_load` decodes each semantic artifact with the unchanged codec into `FeatureCounts` of one `FeaturePool` per load, and the decoded strings are released immediately. This is two lines.
- `hf_artifacts/space/...`: the Space bundle copies of both files.

**Schema and format changes:** none. The codec, payload bytes, artifact keys, the schema (version 2), and the `semantic_features.py` and `codecs.py` sources are unchanged, so all nine extractor fingerprints stay as they were. `semantic.py` is covered by the index fingerprint only, as in Stage 3 and Stage 4: changing it re-runs global assembly, which a build does anyway, and invalidates no artifact.

**Tooling:**

- `stage4_benchmark.py`:
  - `--extra-root NAME=DIR` compares any number of revisions, rotated per round, with one digest required across all of them.
  - Each phase records the AC/battery state before and after it. A phase on battery is `on_battery_suspected` and is excluded like a paging phase.
  - Component memory now follows `__slots__`.
  - Double-encoded characters (`…` and `–` stored as mojibake) are fixed in the generator. They also appear 78 times in PR #28's committed `stage4_benchmark.md`, which this branch does not regenerate.
- `stage4_1_profile.py` / `.json`: the Phase A profile.
- `stage4_1_compatibility.py` / `.json`: the cross-revision cache matrix.
- `stage4_1_query_latency.py`: a repeated warm-engine latency probe, with the garbage collector enabled and disabled. It is written and compiled but **not run**; the benchmark's 75 paired samples per revision answered the question it was written for (§8).
- `stage4_benchmark.py`, later fixes: a thread race in the inherited Stage 2 child's memory probe that failed a phase (calls are now serialised), and `--require-ac`, which waits for 30 s of mains power before every phase.

## 6. End-to-end benchmark

**Run.** `stage4_benchmark.py --require-ac` compared three clean revisions: Stage 3 `60fbfc0` (baseline), Stage 4 `643fa22` (`intern`) and Stage 4.1 `41991e8` (candidate; its code is `1115343` plus the dict-semantics `__eq__`, which no engine path calls).

- **Corpus:** 10,000 reduced files, manifest `4d7140fe…`, the same corpus as Stage 4.
- **Rounds:** 3 rounds with `--verify --component-memory`. Every round ran every revision, rotated so each revision went first once.
- **Conditions:**
  - every phase started and ended on mains power, with the maximum heartbeat gap ≤ 0.8 s;
  - nothing was paging-suspected, suspended or excluded;
  - 4.6 GB was available at the start.
- **Sleep:** the machine slept from 13:04 to 16:45 local time. That was during `--require-ac`'s wait before round 1's first phase, outside every measured phase.
- Raw data: `stage4_1_benchmark.json`; generated summary: `stage4_1_benchmark.md`.

| 10,000 reduced, median (min–max), n = 3 | Stage 3 `60fbfc0` | Stage 4 `643fa22` | **Stage 4.1** |
| :--- | ---: | ---: | ---: |
| Uncached: ready engine | 34.9 s (34.7–63.7) | 39.9 s (38.4–85.8) | **35.5 s** (34.8–36.1) |
| Uncached: semantic fit incl. extraction | 16.65 s | 21.02 s | 16.92 s |
| Cold cached: ready engine | 50.9 s (50.2–120.3) | 57.0 s (55.6–57.7) | **47.5 s** (47.3–49.0) |
| Cold cached: semantic fit | 16.88 s | 20.90 s | 16.80 s |
| Cold cached: persist | 14.9 s | 16.2 s | **11.7 s** |
| Warm restart: ready engine | 21.8 s (21.6–23.3) | 26.8 s (26.4–27.4) | **21.9 s** (21.9–22.6) |
| Warm restart: cache load | 8.7 s | 13.4 s | 11.0 s |
| Warm restart: fit (all indexes) | 6.7 s | 6.2 s | **4.7 s** |
| Warm restart: semantic fit | 3.46 s | 3.12 s | **1.47 s** |
| Query latency median (25 queries per round) | 37.0 ms | 40.9 ms | **36.6 ms** |

**Per-round ratios.**

- Stage 3 / Stage 4.1, ready engine:
  - uncached 1.76, 0.98, 1.00;
  - cold 2.46, 1.07, 1.06;
  - warm 1.03, 0.99, 0.98.
- Stage 4 / Stage 4.1:
  - uncached 2.37, 1.13, 1.10;
  - cold 1.18, 1.20, 1.18;
  - warm 1.21, 1.23, 1.20.
- Round 1's largest values are outliers in the first phases after the machine woke from its 3.7-hour sleep: Stage 3's cold build (120.3 s, with a 41.8 s semantic fit) and Stage 4's uncached build (85.8 s). They are kept, and they fall outside every median. Stage 4.1's three values span ≤ 1.5 s in every phase.

**Reading.**

- **Stage 4.1 is level with Stage 3:** uncached +1.8%, warm +0.8%, both within the spread of the runs. The cold cached build is 6.7% faster, mostly in persisting (14.9 → 11.7 s; the cause was not isolated).
- **Stage 4.1 is faster than Stage 4 in every phase:** uncached −11%, cold −17%, warm −18%. Stage 4's regression against Stage 3 reproduces here (+14%, +12%, +23%).
- **What the warm restart trades:**
  - The cache load is +2.3 s against Stage 3: one pool lookup per decoded pair, the remaining per-pair cost of the unchanged JSON format.
  - The semantic fit is −2.0 s: there is no per-pair Python pass.
  - The two cancel out.

**Earlier, invalid attempts** (kept, labelled):

- `stage4_1_benchmark_battery_round1.json`: the laptop switched to battery during round 1, and the CPU was throttled. Its digests and peak memory are valid.
- `stage4_1_benchmark_flaky_power_round1.json`: power was lost mid-round, and the probe race failed a phase.

**Not measured for Stage 4.1:** 10,000 realistic and 30,000 reduced files (Stage 4's time cost grew with size: +28% cold at 30,000 files), `refresh()` and mutation series at these sizes, and other machines.

## 7. Memory

| 10,000 reduced files | Stage 3 | Stage 4 (`intern`) | **Stage 4.1** |
| :--- | ---: | ---: | ---: |
| Retained index memory, all components (deep sizes, uncached build) | 1,505.7 MB | 860.9 MB (−43%) | **613.1 MB (−59%)** |
| … of which the semantic per-document feature cache | 1,064.9 MB | 421.8 MB | **172.3 MB** |
| String objects held by the feature cache (15,300,236 pairs; 433,475 distinct features) | 15,300,236 | 433,475 | 433,475 |
| Peak working set: uncached / cold / warm (median, n = 3) | 2.05 / 2.08 / 2.37 GB | 1.38 / 1.41 / 1.71 GB | **1.09 / 1.14 / 1.43 GB** |
| Peak committed: uncached / cold / warm | 3.10 / 3.14 / 3.42 GB | 2.44 / 2.47 / 2.77 GB | **2.14 / 2.20 / 2.49 GB** |

- Peak working sets vary by ≤ 0.01 GB across rounds.
- Other components are identical across revisions. The lexical term cache is 98.6 MB, the lexical index 106.1 MB, the abstainer 109.6 MB and the function graph 75–77 MB; they are now the largest remaining structures.
- The component memory was measured before the run's AC wait, on battery. Deep object sizes don't depend on CPU speed.
- Cache database and WAL sizes are unchanged: same payloads.

## 8. Query latency

**Semantic scoring in isolation** (Phase A; five repetitions of the 25-query sample per variant):

- medians were 22.0 to 23.0 ms, and p90 26.8 to 30.3 ms, for every representation;
- the per-document cache is not read at query time.

**End to end** (§6; 75 warm-engine samples per revision: 25 queries × 3 rounds, each round in a fresh process):

| | Stage 3 | Stage 4 | Stage 4.1 |
| :--- | ---: | ---: | ---: |
| Median of round medians | 37.0 ms | 40.9 ms | 36.6 ms |
| All 75 samples: median / p90 | 37.4 / 44.6 ms | 41.5 / 49.6 ms | 36.6 / 44.4 ms |
| Paired per-query ratio against Stage 4.1 (median of 75) | 1.014 | 1.135 | 1 |

**Findings:**

- Stage 4's query-latency regression reproduces: +13.5% paired against Stage 4.1, and +12.9% against Stage 3 (paired ratio 0.886).
- Stage 4.1 removes it: it is level with Stage 3.
- The maximum in every revision (736–744 ms) is each process's first query, which includes one-time initialisation.

**What is not known.** Semantic scoring is identical in all representations, so the Stage 4 regression lies outside the semantic score. One example is the other retrieval stages running on a heap that holds 433,000 interned strings plus the strings freed when duplicates were released. **That cause is not established.** The GC-on/off probe (`stage4_1_query_latency.py`) was not run.

## 9. Correctness and compatibility

- **Index state.** Every Phase A variant produced the identical index digest after a first fit and after a refit on decoded state (`e0f80521…`). In the benchmark (§6), the warm and uncached builds of all three revisions produced one digest, `55b48fb2…`, in all three rounds: 18 of 18 builds. The battery-affected round produced the same digest.
- **Tests.** The tests compare the Stage 4.1 index with the verbatim Stage 2 reference and with fresh builds. They cover:
  - all 165 Stage 3 semantic tests: mutation sequences, lifecycle, numerics under every promotion rule, and the full 225-query harness;
  - 23 Stage 4 / 4.1 tests: pool determinism and append-only ids; `FeatureCounts` keys, values, order, equality, empty documents, counts beyond int32, and a 200,000-feature round trip through the unchanged codec; counts from the loader's pool, another pool and plain dicts; compaction with exact results; warm restart; loader sharing; byte-identical persisted payloads; refresh; and a semantic payload with a duplicated feature and a valid checksum, which is rejected and rebuilt.
- **Cache compatibility** (`stage4_1_compatibility.json`, 1,000 reduced files):
  - Each revision (Stage 3 `60fbfc0`, Stage 4 `643fa22`, Stage 4.1 `e4969e9`) wrote a cache with a cold build, and each revision then warm-restarted on a copy of it.
  - In all **9 of 9** cells, 1,000 of 1,000 files were reused, 0 extracted and 0 artifacts written, with 1,000 semantic cache hits and 0 re-extractions.
  - Every cell's digest and every revision's uncached digest is the same `c2143eb7…`.
  - This covers forward compatibility and rollback to Stage 3 or Stage 4. No migration is needed, because nothing persisted changed.
- **Not measured:** interrupted migration (there is no migration), concurrency (the writer and reader protocol is unchanged and covered by the existing Stage 1 and Stage 2 process tests in CI), and any verification at 10,000 realistic or 30,000 reduced files.

## 10. Tests and CI

| Run | Result |
| :--- | :--- |
| Stage 3 semantic suites (6 files) + Stage 4 file, before the rewrite | 165 passed |
| `tests/test_v2_stage4_scalability.py` (23 tests) + Stage 3 features and reference | 109 passed |
| `test_hf_space_bundle.py`, `test_semantic.py`, `test_stage1_cache_corruption.py` | 47 passed |
| CI on `1115343` (run 44869840195) | **27 of 27 jobs passed** |
| CI on `e4969e9` (run 44873011169) | **27 of 27 jobs passed**: numpy 1.24.4 / SciPy 1.10.1 with legacy and weak promotion, numpy 2.x, Linux / Windows / macOS, Python 3.10–3.12 |
| CI on `e6826f1` (run 44877682860) | **27 of 27 jobs passed** |
| `tests/test_v2_stage4_scalability.py` after the harness fixes (25 tests) | 25 passed |

The full local suite was not re-run, because the machine was on battery; CI runs the whole suite. CI for the final commit is in PR #29's checks.

## 11. Decision matrix (measured values only; 10,000 reduced files; "—" = not measured)

| Design | Memory | Build time | Restart time | Query latency | Compatibility |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Stage 3 dicts (`60fbfc0`) | retained 1,506 MB; peak 2.05 GB | uncached 34.9 s; cold 50.9 s | warm 21.8 s | 37.0 ms | published format |
| Stage 4 `sys.intern` (`643fa22`) | 861 MB; peak 1.38 GB | 39.9 s (+14%); 57.0 s (+12%) | 26.8 s (+23%) | 40.9 ms (+13% paired) | same format; 9/9 matrix |
| Private pool dict (prototype) | representation 437 MB (Phase A) | semantic 8.4 s (Phase A) | semantic 15.2 s (Phase A) | semantic 22.8 ms | same format; — |
| **Stage 4.1 integer ids (built)** | **613 MB (−59%); peak 1.09 GB** | **35.5 s (+1.8%); 47.5 s (−6.7%)** | **21.9 s (+0.8%)** | **36.6 ms (−1.4% paired)** | **same format; 9/9 matrix** |
| ids + persisted binary format (prototype) | representation 159 MB (Phase A) | semantic 5.1 s (Phase A) | semantic decode + refit 2.9 s (Phase A) | 23.0 ms semantic | new codec and generation dictionary; — |

Percentages are against Stage 3. Built revisions are measured end to end (§6, three-round medians); prototypes in Phase A only (§3).

**Remaining work, in order:**

1. Repeated, verified rounds at 10,000 realistic and 30,000 reduced files (`--require-ac`, ≥ 8 GB available), where Stage 4's cost was largest.
2. The cause of Stage 4's query-latency regression, if it matters beyond choosing Stage 4.1 (`stage4_1_query_latency.py`).
3. A design review of a persisted integer-id format. It is the only measured way to remove the JSON decode cost: about 5.6 s of semantic decode at 10,000 files, against 1.2 s for the prototype.
4. The same treatment for the lexical and abstainer per-document caches (205 MB and 110 MB at 10,000 reduced files).
5. Lazy or per-kind generation loading.

## 12. Recommendation for PR #28

- **Do not merge #28 alone.** Its time and latency cost reproduces here (+12% to +23% time, +13% query latency against Stage 3), and this work identifies the cause: per-pair work.
- **Review #28 and #29 as one stack.** #29 keeps #28's benchmark infrastructure and evidence and replaces its `sys.intern` mechanism. At 10,000 reduced files it delivers −59% retained memory, against #28's −43%, at Stage 3 speed and latency.
- **Before merging, run at least one verified round at 30,000 reduced files.** Stage 4's cost grew with size, and Stage 4.1 has not been measured there.
- Merging stays a human decision. Nothing was merged, tagged or released.

## 13. Verdict: PERFORMANCE RECOVERY SUCCESSFUL (at 10,000 reduced files)

**Measured end to end** (three verified rounds, mains power, nothing excluded):

- Stage 4.1 keeps and deepens the memory reduction: retained index memory −59% against Stage 3, against −43% for Stage 4, and peak working set −40% to −47%.
- It removes Stage 4's time and latency cost: uncached +1.8%, cold −6.7%, warm +0.8% and query latency −1.4% against Stage 3, and 11–18% faster than Stage 4 in every phase.
- Results are exact: one digest across 18 builds, and 9/9 cross-revision cache reuse.

**Scope:** the verdict covers the primary workload only. 10,000 realistic and 30,000 reduced files were not measured for Stage 4.1, and nothing is extrapolated to them.
