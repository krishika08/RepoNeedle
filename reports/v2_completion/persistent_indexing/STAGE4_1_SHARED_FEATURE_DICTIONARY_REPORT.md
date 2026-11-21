# V2 Stage 4.1: shared semantic feature dictionary

**Scope:** replace Stage 4's `sys.intern` sharing (PR #28) with a representation that keeps the memory reduction without its time cost, with exact retrieval and no cache invalidation.
**Branch:** `stage4.1/shared-feature-dictionary`, stacked on PR #28 (head `643fa22`). Draft PR #29.
**Machine:** Windows 11, Python 3.12.10, numpy 2.5.2, SciPy 1.18.1, 18 logical CPUs, 16 GB RAM. One machine; nothing here is extrapolated to others.

## 1. Summary

- **Root cause of the Stage 4 time cost** (measured, §3): `sys.intern` itself is not the problem. The cost is one hash-table probe per (document, feature) pair plus a second per-document dict built for every document. That adds +4.9 s when features are extracted and +5.1 s when the cache is decoded, at 10,000 reduced files (15.3 M pairs, 433 k distinct features). A private canonical dict instead of the global intern table costs the same. The garbage collector plays no part: about 120 k tracked objects and a 0.04 s full collection in every variant.
- **Built (§5):** each document's feature counts are int32 ids into one append-only, per-index `FeaturePool` (one string per distinct feature) plus counts, behind a read-only `Mapping` with the dict's exact keys, values and order. `fit()` derives the first-seen order, document frequencies and matrix columns from the ids with array operations; the per-pair Python pass is gone.
- **Unchanged:** persisted payloads, codecs, schema, the nine extractor fingerprints, every index structure and retrieval. Caches written by Stage 3 and Stage 4 are reused with no re-extraction, and caches written by Stage 4.1 are reused by Stage 3 and Stage 4 (§9).
- **Not established: end-to-end performance (§6).** The planned three-round, three-revision 10,000-file benchmark was stopped after one round, because the laptop switched to battery power and Windows throttled the CPU. Its timings are invalid and none are used. No end-to-end time, restart or query-latency improvement is claimed for Stage 4.1. Valid from that round: one identical digest across all six builds, and peak working sets. The candidate's peak was 1.09 / 1.15 / 1.43 GB (uncached / cold / warm), against 1.38 / 1.41 / 1.71 GB for Stage 4 and 2.05 / 2.08 / 2.37 GB for Stage 3.
- **Verdict: PARTIAL IMPROVEMENT — MORE VALIDATION NEEDED** (§13).


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
- `stage4_1_query_latency.py`: a repeated warm-engine latency probe, with the garbage collector enabled and disabled. It is written and compiled but **not run** (§8).

## 6. End-to-end benchmark (not completed)

The run compared three revisions with `stage4_benchmark.py`: Stage 3 `60fbfc0` (baseline), Stage 4 `643fa22` (`intern`) and Stage 4.1 `1115343` (candidate). All three trees were clean. It used the 10,000 reduced-file corpus (manifest `4d7140fe…`, the one used for Stage 4), 3 rounds planned, with `--verify --component-memory`.

The laptop left mains power at about 05:18 UTC, during the baseline's cold build. Every later phase ran 2–3× slower than the same code had on the same corpus in Stage 4. For example, the Stage 3 cold build took 101.9 s against 51.0 s, and the query medians were 72–166 ms against 37 ms. The Stage 3 warm restart also paged: available memory was 3.9 GB at the start, against 7.4 GB in Stage 4.

I stopped the run after round 1, and the waiter for mains power expired with the machine still on battery. Raw data, labelled: `stage4_1_benchmark_battery_round1.json`. It predates the power recording, so its phases carry no `on_battery_suspected` flag; the file's `stage4_1_note` says which parts are valid.

**Not measured for Stage 4.1:** time to a ready engine (uncached, cold, warm), cache load and publish times, end-to-end query latency, 10,000 realistic files, 30,000 reduced files, and repeated rounds. The command to run them:

```
git worktree add <stage3> 60fbfc0 && git worktree add <stage4> 643fa22
python reports/v2_completion/persistent_indexing/stage4_benchmark.py --baseline-root <stage3> \
    --extra-root intern=<stage4> --files 10000 --profile reduced --rounds 3 --verify --component-memory \
    --out stage4_1_benchmark.json          # on mains power, with ≥ 8 GB available
```

## 7. Memory

| 10,000 reduced files | Stage 3 | Stage 4 (`intern`) | Stage 4.1 |
| :--- | ---: | ---: | ---: |
| Per-document semantic representation (Phase A, deep size) | 1,063 MB | 423 MB (−60%) | **159 MB (−85%)** |
| Peak working set, uncached / cold / warm (1 round, §6) | 2.05 / 2.08 / 2.37 GB | 1.38 / 1.41 / 1.71 GB | **1.09 / 1.15 / 1.43 GB** |

- The Stage 3 and Stage 4 peaks reproduce Stage 4's published three-round medians (2.05 → 1.38 GB uncached, 2.37 → 1.71 GB warm).
- The Stage 3 warm peak comes from a phase flagged `paging_suspected`.
- The candidate's whole-engine retained memory per component was not measured validly, because the probe bug is fixed only in `e4969e9`. The representation size above comes from the Phase A deep size instead.

## 8. Query latency

**Semantic scoring.** Phase A, five repetitions of the 25-query sample per variant in one process, gave semantic-score medians of 22.0 to 23.0 ms and p90 of 26.8 to 30.3 ms for every representation, including Stage 3 dicts and Stage 4 interning. The per-document cache is not read at query time. So the representation does not explain Stage 4's end-to-end query-latency increase (+9.5% at 10,000 and +22% at 30,000 files).

**End to end.** Other explanations are open, and each would need repeated warm-engine latency samples on mains power:

- heap layout after a different warm-restart load;
- CPU frequency or contention during the single 25-query pass Stage 4 recorded;
- run-to-run noise.

`stage4_1_query_latency.py` collects exactly that (several processes per revision, interleaved, GC on and off, median/p90/p99), but it was not run, and no cause is claimed.

## 9. Correctness and compatibility

- **Index state.** Every Phase A variant produced the identical index digest after a first fit and after a refit on decoded state (`e0f80521…`). In the stopped benchmark round, the warm and uncached builds of all three revisions produced one digest: `55b48fb2…`, six of six.
- **Tests.** The tests compare the Stage 4.1 index with the verbatim Stage 2 reference and with fresh builds. They cover:
  - all 165 Stage 3 semantic tests: mutation sequences, lifecycle, numerics under every promotion rule, and the full 225-query harness;
  - 23 Stage 4 / 4.1 tests: pool determinism and append-only ids; `FeatureCounts` keys, values, order, equality, empty documents, counts beyond int32, and a 200,000-feature round trip through the unchanged codec; counts from the loader's pool, another pool and plain dicts; compaction with exact results; warm restart; loader sharing; byte-identical persisted payloads; refresh; and a semantic payload with a duplicated feature and a valid checksum, which is rejected and rebuilt.
- **Cache compatibility** (`stage4_1_compatibility.json`, 1,000 reduced files):
  - Each revision (Stage 3 `60fbfc0`, Stage 4 `643fa22`, Stage 4.1 `e4969e9`) wrote a cache with a cold build, and each revision then warm-restarted on a copy of it.
  - In all **9 of 9** cells, 1,000 of 1,000 files were reused, 0 extracted and 0 artifacts written, with 1,000 semantic cache hits and 0 re-extractions.
  - Every cell's digest and every revision's uncached digest is the same `c2143eb7…`.
  - This covers forward compatibility and rollback to Stage 3 or Stage 4. No migration is needed, because nothing persisted changed.
- **Not measured:** interrupted migration (there is no migration), concurrency (the writer and reader protocol is unchanged and covered by the existing Stage 1 and Stage 2 process tests in CI), and digest verification at 10,000 realistic or 30,000 reduced files.

## 10. Tests and CI

| Run | Result |
| :--- | :--- |
| Stage 3 semantic suites (6 files) + Stage 4 file, before the rewrite | 165 passed |
| `tests/test_v2_stage4_scalability.py` (23 tests) + Stage 3 features and reference | 109 passed |
| `test_hf_space_bundle.py`, `test_semantic.py`, `test_stage1_cache_corruption.py` | 47 passed |
| CI on `1115343` (run 44869840195) | **27 of 27 jobs passed** |
| CI on `e4969e9` (run 44873011169) | **27 of 27 jobs passed**: numpy 1.24.4 / SciPy 1.10.1 with legacy and weak promotion, numpy 2.x, Linux / Windows / macOS, Python 3.10–3.12 |

The full local suite was not re-run: the machine was on battery and the time went to the benchmark. CI runs the whole suite.

## 11. Decision matrix (only measured values; "—" = not measured)

| Design | Memory | Build time | Restart time | Query latency | Compatibility |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Stage 3 dicts (`60fbfc0`) | 1,063 MB repr.; peak 2.05 GB uncached | semantic 5.9 s (Phase A) | semantic 10.8 s (Phase A) | semantic 22.1 ms | published format |
| Stage 4 `sys.intern` (`643fa22`) | 423 MB; peak 1.38 GB | semantic 9.3 s; end-to-end +10.6% vs Stage 3 (Stage 4 report) | semantic 14.7 s; +21.7% (Stage 4 report) | semantic 22.0 ms; end-to-end +9.5% (Stage 4 report) | same format, 9/9 matrix |
| private pool dict | 437 MB | semantic 8.4 s | semantic 15.2 s | semantic 22.8 ms | same format (not built) |
| **Stage 4.1 integer ids (built)** | **159 MB; peak 1.09 GB** | **semantic 4.8 s**; end-to-end — | **semantic 10.2 s**; end-to-end — | semantic 22.7 ms; end-to-end — | **same format, 9/9 matrix** |
| ids + persisted binary format (prototype) | 159 MB | semantic 5.1 s | semantic 2.9 s | 23.0 ms | new codec + generation dictionary (not built) |

**Remaining work, in order:**

1. The end-to-end three-round, three-revision benchmark on mains power: 10,000 reduced, then 10,000 realistic and 30,000 reduced if memory allows.
2. The query-latency probe.
3. A design review of a persisted integer-id format. It is the only measured way to remove the JSON decode cost: about 5.6 s of semantic decode at 10,000 files, against 1.2 s for the prototype.
4. The same treatment for the lexical and abstainer per-document caches (205 MB and 110 MB at 10,000 reduced files).
5. Lazy or per-kind generation loading.

## 12. Recommendation for PR #28

- **Do not merge #28 alone.** Its measured time cost stands, and this work shows the cause: per-pair work, not interning.
- **Review #28 and #29 together.** #29 keeps #28's benchmark infrastructure and evidence and replaces its `sys.intern` mechanism. #29's evidence is stronger on memory: 85% less per-document representation than Stage 3, against 60%, and lower peaks than Stage 4. The Phase A profile also shows it removing the extra semantic work. The end-to-end confirmation is still missing.
- **Merge order, if accepted:** #28 then #29, or #29 as a single stack. That should wait until §6 has been run on mains power and shows no end-to-end regression against Stage 3.

## 13. Verdict: PARTIAL IMPROVEMENT — MORE VALIDATION NEEDED

**Established:**
- the root cause of the Stage 4 time cost;
- an exact implementation with an unchanged persisted format, full cross-revision cache compatibility (9/9) and green CI;
- a large memory gain on the representation, plus lower peaks than both Stage 3 and Stage 4 in one round;
- in isolation, semantic work faster than Stage 3 at extraction and fit, and on par at restart.

**Not established:**
- end-to-end time and query latency, because the only full benchmark round ran on battery power and is invalid for timing;
- any result at 10,000 realistic or 30,000 reduced files.

Claiming "performance recovery successful" would need those measurements.
