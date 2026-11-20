# V2 Stage 3: Exact High-Performance Semantic Index Reconstruction

**Branch:** `feat/v2-semantic-exact-reconstruction` (base `0b27381`, the Stage 2 baseline after PR #26). **Package
version:** `1.2.0` (unchanged). **Design:** [PERSISTENT_INDEXING_DESIGN.md](../../../docs/PERSISTENT_INDEXING_DESIGN.md)
§19. **Benchmark data:** [`stage3_benchmark.json`](stage3_benchmark.json), produced by
[`stage3_benchmark.py`](stage3_benchmark.py) against the code of commit `caf0cd4`.

## 1. Summary

- **The semantic index is still recomputed in full on every build** (`global_structures["semantic"] ==
  "recomputed_in_full"`). Stage 3 makes that reconstruction cheaper; it does **not** maintain document frequencies,
  the vocabulary, IDF or the matrix incrementally, and it persists no semantic global state. Incremental document
  frequencies were prototyped, found exact, and rejected because they would save almost nothing (§3).
- **Exactness:** the new `fit()` is bit-identical to a verbatim copy of the Stage 2 implementation
  (`tests/reference_stage2_semantic.py`, SHA-256 pinned): vocabulary order, IDF bytes, raw CSR `indptr`/`indices`/
  `data` arrays and dtypes, score arrays, and the full differential harness on all 225 queries. This holds under numpy
  1.24.4 / SciPy 1.10.1 with legacy and with weak promotion, and under numpy 2.x (CI jobs for all three). In every one
  of the 6 benchmark rounds, the Stage 3 warm restart, the Stage 3 uncached build, the Stage 2 uncached build and the
  Stage 2 warm restart produced the same digest of the complete index state and of retrieval.
- **Measured (1,000 and 2,500 realistic files, three rounds each, Stage 2 re-measured in the same rounds):** the
  semantic phase of every restart was faster with Stage 3 in **all 58 paired restart comparisons** (29 per size);
  it was at least 2× faster in 28 of 29 at 1,000 files and 22 of 29 at 2,500 files. Medians of the warm-restart
  semantic phase: **3.36 s → 1.29 s (2.60×)** at 1,000 files and **11.00 s → 2.56 s (4.30×)** at 2,500 files; time to
  a ready engine **8.3 s → 6.2 s** and **28.5 s → 19.2 s**. The transient memory of one semantic fit **halved**
  (317.4 → 162.7 MB and 784.7 → 391.1 MB); peak process memory was lower in every phase.
- **Variability:** the measurement machine's speed varied by up to 3× between phases, even within a round, without
  paging or suspension (§5.1). The ranges and per-round ratios below are wide, some individual rounds show Stage 3
  slower to a ready engine, and two 2,500-file scenario medians fall below 2× (§5.3). The report gives every round.
- **Not measured:** 10,000 reduced, 10,000 realistic and 30,000 reduced files (runtime and paging constraints; §5.7).
- **Upgrade cost (measured once per size):** the first Stage 3 build over a Stage 2 cache re-extracts exactly the
  semantic artifacts (1,000 and 2,500 written) and reuses everything else, including every graph resolution (§5.6).
- No cache schema change, no new persisted state, no retrieval or ranking change, no new dependency.

## 2. What changed

### 2.1 The single-pass reconstruction (`reponeedle/core/semantic.py`)

`SubwordSemanticIndex.fit()` recomputes every global semantic structure on every call, as before. Design §19.2
describes the algorithm; in short:

| Step | Stage 2 | Stage 3 | Exactness argument |
| :--- | :--- | :--- | :--- |
| Per-document counts | signature-validated cache, else extraction | unchanged (extraction moved to `semantic_features.py`) | same functions, same order |
| Document frequencies | Python loop over every pair, `df[f] = df.get(f, 0) + 1` | one C-level pass `map(first_ticket.setdefault, counts, ticket)`; dense ids by a gather through a ticket-to-id array; `bincount` | the dict's insertion order is the Stage 2 `df_counts` order; a document's counts hold each feature once |
| Vocabulary | `sorted(df.items(), key=(df, len), reverse=True)[:max_features]` | `np.lexsort((first_seen_index, -len, -df))[:max_features]` | Python's sort is stable with `reverse=True`, so ties keep first-seen order; the first-seen index makes the key total |
| IDF | scalar `math.log` per vocabulary entry into float32 | the same loop | identical expression |
| Matrix values | Python loop appending `(1.0 + math.log(cnt)) * idf[c]` (a float times a float32 scalar) | TF from the same expression once per distinct count (dense table); product by the run-time promotion rule, with a sampled check against the scalar expression | the product rule is detected from the expression itself on every fit; a mismatch or unknown rule uses the scalar expression for every value |
| CSR construction | `sparse.csr_matrix((data, (rows, cols)), shape, dtype=float32)` from lists | the same call from arrays, same entry order | identical input to the same constructor |
| Normalisation | `sparse.linalg.norm`, zero norms to 1, `multiply`, `tocsr` | unchanged | identical calls |

**The numeric product.** The Stage 2 values are a Python float times a numpy float32 scalar. numpy 2.x, and numpy
1.x under `NPY_PROMOTION_STATE=weak`, compute that in float32; numpy 1.x with legacy promotion computes it in float64
and the CSR constructor rounds the result to float32. On 300 documents of the 1,000-file corpus the two rules
disagree on 40,647 of 1,000,176 values (4.1%), so neither can be hard-coded. Every fit evaluates `1.0 * np.float32(1.0)` and uses the matching
vectorised rule, then re-evaluates 64 sampled values with the scalar expression; a disagreement (or an unrecognised
result type) switches to the scalar expression for every value. `fit_stats["product_rule"]` reports the rule used.

**The final matrix.** It does not have sorted indices (the diagonal product in `multiply` produces that layout), and
its dtype is what SciPy's row norm returns: float64 under SciPy 1.18, float32 under SciPy 1.10. Because Stage 3 calls
the same functions on an identical pre-normalised matrix, both properties match the Stage 2 reference in every
environment; the tests compare the raw arrays and their dtypes.

### 2.2 Per-document extraction module and the fingerprint (`reponeedle/core/semantic_features.py`)

Feature text (path, symbols, the first 8,000 characters), word and character n-gram features, counts in
first-occurrence order, `doc_signature` and `FEATURES_SIGNATURE_VERSION` moved unchanged into a module of their own.
`SubwordSemanticIndex` binds these functions directly (`_extract_features = semantic_features.extract_features`,
etc.; a test asserts identity), so no extraction logic remains in `semantic.py`, and a test asserts that
`semantic.py` contains none of its markers.

The `semantic` artifact's extractor fingerprint now covers `semantic_features`, the tokenizer, the signature
encoding and the codec; `semantic.py` is covered only by the index fingerprint. Effects:
- **one-time invalidation**: a Stage 3 build over a Stage 1 or Stage 2 cache re-extracts every semantic artifact and
  reuses every other one (measured in §5.4). It is a normal published build, not a rebuild from scratch;
- later edits to the global assembly invalidate no per-file artifact (tested by simulating source changes of each
  module).

Every other extractor fingerprint is byte-for-byte the Stage 2 one: both checkouts computed all nine fingerprints in
one interpreter, and only `semantic` differs. An earlier revision of this branch had edited docstrings in
`engine.py` and `models.py`, whose source is part of the document-metadata fingerprint; upgrading a 1,000-file cache
then rewrote 2,000 artifacts instead of 1,000. Those files are now unchanged from Stage 2.

### 2.3 Diagnostics

`fit_stats` (last fit only; never index state, never compared) and `IndexUpdateReport.work_counters["semantic"]`
(cached, refreshed and uncached routes) report: documents; feature-cache hits and misses; documents re-extracted;
document-feature pairs; distinct features; vocabulary size; matrix non-zeros; IDF entries computed; the product rule
and the number of self-checked values; vocabulary entries added and removed relative to the previous fit in the same
process (`None` in a fresh process); and sub-stage timings (feature collection, feature counting, vocabulary
selection, IDF, matrix assembly, normalisation, total). The stage label stays `recomputed_in_full`, with the reason
"recomputed in full by design (V2 Stage 3: exact single-pass reconstruction; document frequencies, vocabulary, IDF
and the matrix are not maintained incrementally)".

### 2.4 What did not change

No change to retrieval, BM25, the graphs, score fusion, routing, CUD-Pack, token budgets, discovery order, MCP or the
CLI. No cache schema change (version 2), no new artifact kind, codec or global-state row, no new runtime dependency.
`engine.py` and `models.py` are byte-identical to Stage 2. Package version `1.2.0`.

## 3. Why the semantic index is still recomputed in full

The Stage 3 brief that preceded this implementation planned document frequencies by delta with exact vocabulary
maintenance (design §9.3). The feasibility audit prototyped it: document frequencies by delta; the first-seen order
kept as per-document groups; features whose first document lost them re-resolved by a scan of unchanged documents;
a full fallback when the relative order of surviving documents changes. It was exact (0 mismatches in dictionary
order, first documents and groups over 59 checked random mutation steps) and cost 0.11–0.23 s for a one-file change
against 0.51 s for a full counting pass at 1,000 files (slower than recounting at 10% modified). It was rejected
because the matrix must be rebuilt from every (document, feature) pair whenever N, an IDF value or a column changes,
which is almost every change, and the single-pass fit counts document frequencies inside that same pass: the
incremental table would save the counting step alone while adding its decoding (0.09–0.31 s measured), an encode on
every publish, a privacy fallback and a new class of consistency failures. Row reuse and a persisted matrix were
rejected for the same reason (design §19.1).

## 4. Tests and exactness evidence

165 new tests in six suites; every comparison is exact (bytes, dtypes, order), with no tolerance.

| Suite | Tests | What it establishes |
| :--- | ---: | :--- |
| `test_v2_stage3_semantic_reference.py` | 77 | The reference is the verbatim Stage 2 module (SHA-256); every structure and score array equals it over 9 corpora (fixture repository and its reversal, tie corpora, seeded random corpora, empty, single, feature-less and repeated-feature documents) × 8 configurations (`max_features` 0, 1, 37, 50, default; `min_n`/`max_n` variants including an empty n-gram range); repeated in-place refits; and the **whole engine with the reference semantic index on all 225 queries** (every ranker, abstention, change impact, CUD-Pack). These tests were committed first and passed against the unmodified Stage 2 code. |
| `test_v2_stage3_semantic_numerics.py` | 26 | Every stored matrix value equals the scalar expression after float32 conversion; the pre-normalised matrix (captured at `sparse.linalg.norm`) equals the reference's; a forced wrong or unknown product rule is caught by the self-check and falls back to the scalar expression; the two vectorised rules really differ on the corpus; the dense-table and `np.unique` TF paths; index dtypes chosen by SciPy; boundary cases. |
| `test_v2_stage3_semantic_features.py` | 9 | Direct binding of the extraction functions; unchanged feature text, n-grams, count order and signatures; the 8,000-character limit; the `semantic` fingerprint covers `semantic_features` and not `semantic.py`; an extraction change re-extracts only semantic artifacts; a global-assembly change re-extracts nothing. |
| `test_v2_stage3_semantic_diagnostics.py` | 6 | `fit_stats` contents and churn counters; work counters on cached, refreshed and uncached routes; the `recomputed_in_full` label; diagnostics are not index state; no semantic global state, schema version 2 and the same tables and artifact kinds. |
| `test_v2_stage3_semantic_mutations.py` | 36 | 11 mutations (body edit, feature edit, symbol edit, add, delete, rename, multiple, df increase and decrease, vocabulary churn, ties) × 2 configurations (default and `max_features=60`, where cutoff transitions really occur) through `refresh()` and a warm restart; first-seen provider deletion; discovery-order reversal and restoration; empty repository and back; `max_features`/`min_n`/`max_n` changes between builds; `persist_exclude` transitions; seeded random sequences. Each state is compared with a fresh uncached build (full harness, query sample) **and** with the Stage 2 reference. |
| `test_v2_stage3_semantic_lifecycle.py` | 11 | New cache, warm restart, `refresh()`, `update_documents()`, `remove_documents()`; fresh processes under `PYTHONHASHSEED` 0 and 1 (one digest for cached and uncached builds under both seeds: the semantic index does not depend on the hash seed); a corrupt semantic artifact; a crash at each publish step; concurrent writers and a reader; read-only load of a version-2 database. |

A Stage 1 test that asserted that editing `semantic.py` changes the semantic fingerprint was updated to the new
module (and now also asserts that editing `semantic.py` changes no per-file fingerprint).

**CI** adds a `semantic-compat` job (numpy 1.24.4 / SciPy 1.10.1 with `NPY_PROMOTION_STATE=legacy` and `weak`, and
numpy 2.x on Python 3.12; each asserts the product rule it expects) running the semantic reference, Stage 1–3 and
equivalence suites, and adds the Stage 3 suites and the equivalence harness to the index-cache job. CI results for
the final commit are in the PR.

**Local runs (Windows, Python 3.12, numpy 2.5.2, SciPy 1.18.1):** the full suite on the final tree: **1,442 passed,
16 skipped, 1 failed**, with `tests/test_public_api.py` excluded. Both exceptions are environment failures that occur
identically at the Stage 2 baseline: an incompatible local FastAPI/Starlette pair stops `api.py` from importing, so
`test_public_api.py` cannot be collected; and `test_stage3_15_safeguards.py::test_missing_dataset_fails_closed`
fails on a Windows console-encoding mismatch in a research script. CI runs both. Skips are optional extras and
Windows symlink and POSIX-permission tests. An earlier full run also found a documentation-consistency failure in
this branch's roadmap wording; it was fixed. Under
numpy 1.24.4 / SciPy 1.10.1 (Python 3.11), the Stage 3 and semantic suites passed with legacy and with weak promotion,
and the Stage 0–2 cache suites passed with legacy promotion (443 passed; the one failure was the fingerprint test
updated above).

## 5. Benchmark

### 5.1 Method and conditions

`stage3_benchmark.py` generates the Stage 1 seeded corpus and runs, per round and per code version, on a pristine
copy: an isolated semantic fit (best of three warm fits and a tracemalloc transient peak); uncached build; cold cached
build; unchanged warm restart; then a restart after each of: a one-file feature edit, a one-file addition, a one-file
deletion, 1% and 10% of the Python files modified, a vocabulary-cutoff transition (three files repeating the words
ranked just outside the 15,000-feature cutoff), a reversed discovery order and its restoration; and an in-process
`refresh()` after a one-file edit. Every phase runs in a fresh process and records the time to a ready engine, the
wall time of every semantic `fit()` call, the engine's work counters, peak working set and committed memory, and the
peak WAL. **Stage 2 (`0b27381`, a git worktree) and Stage 3 run in the same rounds, alternating which goes first**,
with the same corpus, Python, numpy and SciPy, cache settings and machine. A verification step builds a Stage 3 warm
restart, a Stage 3 uncached build, a Stage 2 uncached build and a Stage 2 warm restart under `PYTHONHASHSEED=0` and
compares the digests of their complete index state and retrieval.

**Machine:** Windows 11, Python 3.12.10, numpy 2.5.2, SciPy 1.18.1, SQLite 3.49.1, 15.5 GB of RAM (about 2–5 GB
available during the runs). It was not otherwise idle.

**Earlier attempts, discarded.** Three earlier attempts are not used: (a) one measured a revision whose docstring
edits in `engine.py` and `models.py` also invalidated document-metadata artifacts on upgrade (fixed in `49edb52`);
(b) one was suspended by Modern Standby: the Windows event log showed the machine entering Modern Standby repeatedly
while idle (and sleeping for 7 hours), which suspends desktop processes, and phases took up to 535 s instead of about
15 s; (c) one clean run of the revision before `caf0cd4` measured a 1,000-file warm-restart semantic phase only
1.94× faster than Stage 2 (3.32 s → 1.71 s, three rounds), below the 2× target, which led to the two exact changes of
`caf0cd4` (a gather instead of `searchsorted`, a dense TF table instead of `np.unique`), after which the benchmark was
restarted from scratch. The final run therefore (1) asks Windows to stay awake with the
display on for the benchmark's lifetime (`SetThreadExecutionState`; no setting changed); (2) runs a heartbeat thread
in every phase and excludes any phase with a gap above 5 s (none had one: the largest gap was 4.3 s, in a Stage 2
isolated fit at 2,500 files); (3) records the sleep and Modern Standby events logged during each workload: **none**
for either workload. No number from the earlier attempts is used in the tables.

**Paging.** A phase whose committed memory exceeded the physical memory available when it started is
`paging_suspected` and excluded from the primary comparison (medians and ratios). Three phases were excluded, all
in-process refreshes, which hold the previous engine in memory while loading the next (§5.5). They remain in the raw
data:
- 1,000 files, round 2, **Stage 2** in-process refresh: 20.2 s (committed 2.50 GB against 2.15 GB available);
- 2,500 files, round 3, Stage 2 in-process refresh: 35.8 s (4.66 GB against 4.42 GB);
- 2,500 files, round 3, Stage 3 in-process refresh: 36.6 s (4.49 GB against 3.88 GB).

**Remaining variability.** Without paging or suspension, the machine's speed still varied by up to about 3× between
phases, including between the Stage 2 and Stage 3 phases of the same round, which run minutes apart. Round 2 at
1,000 files ran Stage 2's restarts during a slow period (about 10 s against 3.3 s elsewhere); at 2,500 files,
round 1 was slow for Stage 2 and round 3 for both versions, Stage 3 more so (its uncached build took 108 s against
33–35 s in the other rounds). These rounds are **kept**: the tables give medians, ranges, every round and the ratio
within each round. A supplementary in-process paired measurement intended to control for this drift was interrupted
and is **not** part of the evidence.

### 5.2 1,000 realistic files (3 rounds; 9.2 MB of source; 4,042,988 document-feature pairs, 234,780 distinct features, 3,330,394 non-zeros)

Median (range) over the rounds. "Semantic fit" is the wall time of the semantic index's `fit()` inside the phase;
in uncached and cold builds it includes the unchanged per-document feature extraction.

| Phase | Stage 2 semantic fit | Stage 3 semantic fit | Median ratio | Stage 2 ready engine | Stage 3 ready engine |
| :--- | ---: | ---: | ---: | ---: | ---: |
| uncached build | 11.07 s (10.49–14.52) | 8.13 s (7.88–10.80) | 1.36× | 21.2 s (19.7–27.2) | 18.0 s (17.6–24.5) |
| cold cached build | 10.92 s (10.75–14.58) | 8.00 s (7.98–8.41) | 1.36× | 24.0 s (23.2–30.7) | 20.7 s (20.6–23.4) |
| warm restart, unchanged | 3.36 s (3.31–4.77) | 1.29 s (1.20–3.63) | 2.60× | 8.3 s (8.1–11.0) | 6.2 s (5.9–13.4) |
| one-file feature edit | 3.35 s (3.24–10.68) | 1.23 s (1.21–3.61) | 2.72× | 8.3 s (8.1–18.2) | 6.1 s (5.9–10.9) |
| one-file addition | 3.30 s (3.29–10.63) | 1.26 s (1.18–1.26) | 2.62× | 8.2 s (8.2–20.0) | 6.3 s (6.1–6.6) |
| one-file deletion | 3.46 s (3.31–7.65) | 1.34 s (1.26–1.49) | 2.58× | 8.4 s (8.4–15.5) | 6.5 s (6.0–6.9) |
| 1% of Python files modified | 3.41 s (3.30–10.38) | 1.24 s (1.19–1.30) | 2.75× | 8.3 s (8.2–21.5) | 6.2 s (6.2–6.8) |
| 10% modified | 3.84 s (3.78–10.37) | 1.58 s (1.51–1.59) | 2.43× | 10.3 s (9.6–24.4) | 7.5 s (7.4–7.6) |
| vocabulary-cutoff transition | 3.53 s (3.36–9.99) | 1.26 s (1.24–1.77) | 2.79× | 8.3 s (8.3–20.4) | 6.3 s (6.1–7.5) |
| discovery order reversed | 3.43 s (3.22–9.92) | 1.21 s (1.20–1.43) | 2.84× | 9.5 s (8.7–21.9) | 6.9 s (6.8–7.5) |
| original order restored | 3.40 s (3.25–10.10) | 1.22 s (1.22–1.64) | 2.78× | 9.3 s (8.7–21.7) | 6.9 s (6.8–8.0) |
| in-process refresh (Stage 2: 2 rounds) | 3.40 s (3.19–3.60) | 1.23 s (1.13–3.51) | 2.76× | 8.4 s (8.1–8.7) | 6.1 s (5.9–10.4) |

Every round, semantic fit, Stage 2 / Stage 3 (s; `x` = excluded):

| Phase | Round 1 (Stage 2 first) | Round 2 (Stage 3 first) | Round 3 (Stage 2 first) |
| :--- | ---: | ---: | ---: |
| uncached build | 11.07 / 8.13 | 14.52 / 10.80 | 10.49 / 7.88 |
| cold cached build | 10.92 / 8.00 | 14.58 / 8.41 | 10.75 / 7.98 |
| warm restart, unchanged | 3.31 / 1.20 | 4.77 / 3.63 | 3.36 / 1.29 |
| one-file feature edit | 3.35 / 1.21 | 10.68 / 3.61 | 3.24 / 1.23 |
| one-file addition | 3.29 / 1.18 | 10.63 / 1.26 | 3.30 / 1.26 |
| one-file deletion | 3.31 / 1.34 | 7.65 / 1.49 | 3.46 / 1.26 |
| 1% of Python files modified | 3.30 / 1.19 | 10.38 / 1.30 | 3.41 / 1.24 |
| 10% modified | 3.84 / 1.51 | 10.37 / 1.59 | 3.78 / 1.58 |
| vocabulary-cutoff transition | 3.36 / 1.24 | 9.99 / 1.77 | 3.53 / 1.26 |
| discovery order reversed | 3.43 / 1.21 | 9.92 / 1.43 | 3.22 / 1.20 |
| original order restored | 3.40 / 1.22 | 10.10 / 1.64 | 3.25 / 1.22 |
| in-process refresh | 3.60 / 1.13 | 10.13 x / 3.51 | 3.19 / 1.23 |

Every round, time to a ready engine, Stage 2 / Stage 3 (s):

| Phase | Round 1 | Round 2 | Round 3 |
| :--- | ---: | ---: | ---: |
| uncached build | 21.2 / 18.0 | 27.2 / 24.5 | 19.7 / 17.6 |
| cold cached build | 24.0 / 20.6 | 30.7 / 23.4 | 23.2 / 20.7 |
| warm restart, unchanged | 8.1 / 5.9 | 11.0 / 13.4 | 8.3 / 6.2 |
| one-file feature edit | 8.3 / 5.9 | 18.2 / 10.9 | 8.1 / 6.1 |
| one-file addition | 8.2 / 6.1 | 20.0 / 6.6 | 8.2 / 6.3 |
| one-file deletion | 8.4 / 6.5 | 15.5 / 6.9 | 8.4 / 6.0 |
| 1% of Python files modified | 8.3 / 6.2 | 21.5 / 6.8 | 8.2 / 6.2 |
| 10% modified | 10.3 / 7.4 | 24.4 / 7.5 | 9.6 / 7.6 |
| vocabulary-cutoff transition | 8.3 / 6.3 | 20.4 / 7.5 | 8.3 / 6.1 |
| discovery order reversed | 9.5 / 6.9 | 21.9 / 7.5 | 8.7 / 6.8 |
| original order restored | 9.3 / 6.8 | 21.7 / 8.0 | 8.7 / 6.9 |
| in-process refresh | 8.7 / 5.9 | 20.2 x / 10.4 | 8.1 / 6.1 |

Semantic-fit speed-up within each round (Stage 2 / Stage 3):

| Phase | Round 1 | Round 2 | Round 3 |
| :--- | ---: | ---: | ---: |
| uncached build | 1.36× | 1.34× | 1.33× |
| cold cached build | 1.36× | 1.73× | 1.35× |
| warm restart, unchanged | 2.75× | 1.31× | 2.60× |
| one-file feature edit | 2.76× | 2.96× | 2.63× |
| one-file addition | 2.80× | 8.45× | 2.62× |
| one-file deletion | 2.46× | 5.13× | 2.75× |
| 1% of Python files modified | 2.77× | 7.99× | 2.75× |
| 10% modified | 2.53× | 6.54× | 2.40× |
| vocabulary-cutoff transition | 2.71× | 5.63× | 2.79× |
| discovery order reversed | 2.84× | 6.92× | 2.68× |
| original order restored | 2.80× | 6.16× | 2.66× |
| in-process refresh | 3.20× | – (excluded) | 2.59× |

Round 2's large ratios (5–8×) and its 1.31× warm restart reflect the slow periods described in §5.1, not the code.
Isolated warm fit (best of three, one process per version): Stage 2 3.40 / 4.70 / 3.75 s, Stage 3 1.17 / 1.18 /
1.24 s.

### 5.3 2,500 realistic files (3 rounds; 22.7 MB of source; 10,148,164 pairs, 399,347 distinct features, 8,370,518 non-zeros)

| Phase | Stage 2 semantic fit | Stage 3 semantic fit | Median ratio | Stage 2 ready engine | Stage 3 ready engine |
| :--- | ---: | ---: | ---: | ---: | ---: |
| uncached build | 44.97 s (21.85–45.90) | 16.54 s (15.40–52.61) | 2.72× | 77.4 s (41.1–93.7) | 35.3 s (33.5–108.2) |
| cold cached build | 38.92 s (21.93–51.83) | 19.62 s (16.10–56.76) | 1.98× | 83.4 s (47.6–108.2) | 64.3 s (40.9–120.4) |
| warm restart, unchanged | 11.00 s (6.66–16.46) | 2.56 s (2.33–8.38) | 4.30× | 28.5 s (16.3–36.0) | 19.2 s (11.8–33.9) |
| one-file feature edit | 10.85 s (6.74–16.12) | 2.33 s (2.33–3.39) | 4.65× | 27.9 s (16.5–35.5) | 12.0 s (11.8–17.1) |
| one-file addition | 11.06 s (6.68–16.53) | 2.35 s (2.34–8.07) | 4.70× | 27.6 s (16.6–36.1) | 12.0 s (11.8–37.1) |
| one-file deletion | 11.17 s (6.69–15.93) | 2.35 s (2.30–7.95) | 4.76× | 28.7 s (16.7–35.2) | 12.2 s (11.9–36.3) |
| 1% of Python files modified | 11.15 s (7.00–15.34) | 2.67 s (2.44–7.74) | 4.17× | 28.8 s (17.4–34.5) | 13.5 s (12.3–37.1) |
| 10% modified | 12.61 s (7.76–18.43) | 5.11 s (3.09–10.27) | 2.47× | 32.3 s (19.5–40.0) | 17.2 s (14.7–44.4) |
| vocabulary-cutoff transition | 10.98 s (6.87–14.69) | 5.97 s (2.39–7.62) | **1.84×** | 27.9 s (17.0–32.8) | 19.9 s (12.2–32.7) |
| discovery order reversed | 11.45 s (6.64–15.01) | 5.97 s (2.38–7.80) | **1.92×** | 31.1 s (17.9–35.0) | 29.0 s (13.4–40.6) |
| original order restored | 11.15 s (6.61–16.83) | 5.49 s (2.37–7.78) | 2.03× | 30.4 s (17.6–39.4) | 28.1 s (13.4–28.4) |
| in-process refresh (2 rounds each) | 8.72 s (6.39–11.05) | 3.38 s (2.38–4.38) | 2.58× | 22.1 s (16.1–28.1) | 16.9 s (12.1–21.7) |

Every round, semantic fit, Stage 2 / Stage 3 (s; `x` = excluded):

| Phase | Round 1 (Stage 2 first) | Round 2 (Stage 3 first) | Round 3 (Stage 2 first) |
| :--- | ---: | ---: | ---: |
| uncached build | 44.97 / 15.40 | 21.85 / 16.54 | 45.90 / 52.61 |
| cold cached build | 38.92 / 19.62 | 21.93 / 16.10 | 51.83 / 56.76 |
| warm restart, unchanged | 11.00 / 2.56 | 6.66 / 2.33 | 16.46 / 8.38 |
| one-file feature edit | 10.85 / 2.33 | 6.74 / 2.33 | 16.12 / 3.39 |
| one-file addition | 11.06 / 2.34 | 6.68 / 2.35 | 16.53 / 8.07 |
| one-file deletion | 11.17 / 2.30 | 6.69 / 2.35 | 15.93 / 7.95 |
| 1% of Python files modified | 11.15 / 2.67 | 7.00 / 2.44 | 15.34 / 7.74 |
| 10% modified | 12.61 / 5.11 | 7.76 / 3.09 | 18.43 / 10.27 |
| vocabulary-cutoff transition | 10.98 / 5.97 | 6.87 / 2.39 | 14.69 / 7.62 |
| discovery order reversed | 11.45 / 5.97 | 6.64 / 2.38 | 15.01 / 7.80 |
| original order restored | 11.15 / 5.49 | 6.61 / 2.37 | 16.83 / 7.78 |
| in-process refresh | 11.05 / 4.38 | 6.39 / 2.38 | 16.59 x / 8.07 x |

Every round, time to a ready engine, Stage 2 / Stage 3 (s):

| Phase | Round 1 | Round 2 | Round 3 |
| :--- | ---: | ---: | ---: |
| uncached build | 93.7 / 33.5 | 41.1 / 35.3 | 77.4 / 108.2 |
| cold cached build | 83.4 / 64.3 | 47.6 / 40.9 | 108.2 / 120.4 |
| warm restart, unchanged | 28.5 / 19.2 | 16.3 / 11.8 | 36.0 / 33.9 |
| one-file feature edit | 27.9 / 11.8 | 16.5 / 12.0 | 35.5 / 17.1 |
| one-file addition | 27.6 / 11.8 | 16.6 / 12.0 | 36.1 / 37.1 |
| one-file deletion | 28.7 / 11.9 | 16.7 / 12.2 | 35.2 / 36.3 |
| 1% of Python files modified | 28.8 / 13.5 | 17.4 / 12.3 | 34.5 / 37.1 |
| 10% modified | 32.3 / 17.2 | 19.5 / 14.7 | 40.0 / 44.4 |
| vocabulary-cutoff transition | 27.9 / 19.9 | 17.0 / 12.2 | 32.8 / 32.7 |
| discovery order reversed | 31.1 / 29.0 | 17.9 / 13.4 | 35.0 / 40.6 |
| original order restored | 30.4 / 28.1 | 17.6 / 13.4 | 39.4 / 28.4 |
| in-process refresh | 28.1 / 21.7 | 16.1 / 12.1 | 35.8 x / 36.6 x |

Semantic-fit speed-up within each round (Stage 2 / Stage 3):

| Phase | Round 1 | Round 2 | Round 3 |
| :--- | ---: | ---: | ---: |
| uncached build | 2.92× | 1.32× | 0.87× |
| cold cached build | 1.98× | 1.36× | 0.91× |
| warm restart, unchanged | 4.30× | 2.86× | 1.97× |
| one-file feature edit | 4.65× | 2.90× | 4.75× |
| one-file addition | 4.74× | 2.84× | 2.05× |
| one-file deletion | 4.85× | 2.85× | 2.00× |
| 1% of Python files modified | 4.17× | 2.87× | 1.98× |
| 10% modified | 2.47× | 2.51× | 1.79× |
| vocabulary-cutoff transition | 1.84× | 2.87× | 1.93× |
| discovery order reversed | 1.92× | 2.79× | 1.93× |
| original order restored | 2.03× | 2.79× | 2.16× |
| in-process refresh | 2.52× | 2.68× | – (both excluded) |

Round 2 (the round with the least drift: Stage 2 restarts of 16–20 s to a ready engine) shows 2.5–2.9× for every
restart. In round 3, Stage 3's phases ran in a slower period than Stage 2's (Stage 3's uncached build took 108 s,
against 33–35 s in rounds 1 and 2); the uncached and cold ratios below 1 there come from that drift: the uncached
semantic fit is mostly the unchanged extraction code, which ran 1.3× faster in rounds 1 and 2. Isolated warm fit
(best of three): Stage 2 24.45 / 6.90 / 6.80 s, Stage 3 2.86 / 2.49 / 6.11 s.

### 5.4 Where the Stage 3 semantic fit spends its time (warm restart, median of rounds, ms)

| Workload | Feature collection | Feature counting (single pass) | Vocabulary selection | IDF | Matrix assembly | Normalisation | Total |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 realistic | 15.4 | 712.3 | 30.0 | 5.4 | 350.1 | 170.0 | 1,291.3 |
| 2,500 realistic | 26.5 | 1,676.2 | 37.8 | 3.2 | 592.2 | 206.5 | 2,555.6 |

The single pass over every (document, feature) pair is now the largest part; it is inherent to recomputing the
index from per-document counts (§3). Product rule: `float32` (numpy 2.5.2) with 64 self-checked values in every fit.
The Stage 2 fit has no sub-stage counters.

### 5.5 Memory, database and WAL (medians)

| Workload | Version | Semantic fit transient peak (tracemalloc) | Peak working set: uncached / warm restart / in-process refresh | Peak committed: uncached / warm restart / refresh | Database after cold build / after the series | Peak WAL, cold build; WAL after builds |
| :--- | :--- | ---: | :--- | :--- | :--- | :--- |
| 1,000 realistic | Stage 2 | 317.4 MB | 0.82 / 0.93 / 1.46 GB | 1.88 / 1.99 / 2.52 GB | 27.8 / 28.2 MB | 7.8 MB; 0 |
| | Stage 3 | 162.7 MB | 0.64 / 0.75 / 1.37 GB | 1.69 / 1.80 / 2.43 GB | 27.8 / 28.2 MB | 7.8 MB; 0 |
| 2,500 realistic | Stage 2 | 784.7 MB | 1.91 / 2.17 / 3.55 GB | 2.98 / 3.24 / 4.62 GB | 69.5 / 70.4 MB | 8.0 MB; 0 |
| | Stage 3 | 391.1 MB | 1.46 / 1.72 / 3.37 GB | 2.52 / 2.77 / 4.43 GB | 69.5 / 70.5 MB | 8.0 MB; 0 |

The semantic fit's transient allocation halved and its retained memory is unchanged (39.0 vs 39.1 MB; 96.7 vs
96.8 MB). Database and WAL sizes are the same, as expected without a schema or payload change.

### 5.6 Upgrade: the first Stage 3 build over a cache written by Stage 2 (one measurement per size)

| Workload | Stage 2 cold cached | Stage 2 warm restart | **Stage 3 first build over the Stage 2 cache** | Stage 3 restart after it |
| :--- | ---: | ---: | ---: | ---: |
| 1,000 realistic | 31.9 s | 8.3 s | **14.0 s** | 8.9 s |
| 2,500 realistic | 152.8 s | 50.3 s | **86.8 s** | 36.8 s |

In both, the upgrade build re-extracted exactly the semantic artifacts (1,000 and 2,500 feature-cache misses and
artifacts written), re-resolved no function-graph or repository-graph file, and published normally (no rebuild from
scratch). These are single measurements taken after the rounds; the 2,500-file one ran during a slow period (its
Stage 2 cold build took 152.8 s against an 83.4 s median in the rounds), so it shows the work done, not a
representative duration.

### 5.7 Workloads not measured

| Workload | Status | Reason |
| :--- | :--- | :--- |
| 10,000 reduced files | **Not measured** | Runtime constraints: the clean run was stopped after the 2,500-file workload. Earlier attempts that reached it were affected by Modern Standby or measured an older revision; they are not used. |
| 10,000 realistic files | **Not measured** | Runtime and paging constraints (the Stage 2 report's runs at this size were paging-affected and took hours). |
| 30,000 reduced files | **Not measured** | Runtime and paging constraints. |
| 100,000 files | **Not measured** | As in Stages 1 and 2: the in-memory index exceeds this machine. |

No figure in this report is extrapolated to these sizes.

### 5.8 Relation to the Stage 2 report's figures

The Stage 2 report measured a Stage 2 warm restart of 17.4 s at 1,000 files and 50.7 s at 2,500 files; the Stage 2
code re-measured here took a median of 8.3 s and 28.5 s. The Stage 2 report already described that machine as not
idle; this work found that it also entered Modern Standby when idle, which suspends processes, and the Stage 2
campaign was not checked for it. Those figures are therefore not comparable with the ones here, and **Stage 3 is
compared only with the Stage 2 code re-measured in the same rounds.**

## 6. Acceptance criteria

| # | Criterion | Result |
| :--- | :--- | :--- |
| 1 | Semantic output exactly equivalent to the Stage 2 reference | **Met** (§4; 6 of 6 benchmark rounds with identical four-way digests) |
| 2 | Complete retrieval equivalence harness passes | **Met** locally; final-commit CI in the PR |
| 3 | All CI jobs pass | See the PR (checked on the final commit) |
| 4 | Semantic phase at least 2× faster at 1,000 and 2,500 realistic files against the fresh Stage 2 baseline | **Met at 1,000 files** on the median of every restart scenario (2.43–2.84×; warm restart 2.60×). **Partially met at 2,500 files**: the warm-restart median is 4.30× and 8 of 10 restart-scenario medians are at least 2×, but the vocabulary-cutoff (1.84×) and discovery-reversal (1.92×) medians are below 2×, and 7 of 29 paired restart comparisons were below 2× (minimum 1.79×). Stage 3 was faster in all 58 paired restart comparisons. Given the machine's drift (§5.1), these measurements do not establish 2× for every scenario at 2,500 files. |
| 5 | Clean warm restarts no slower than Stage 2 | **Met on medians** in every restart scenario at both sizes. Not in every individual round: 6 of 58 paired restart comparisons show Stage 3 slower to a ready engine (by up to 22%), each in a round where Stage 3's phases ran in a slower period (§5.2, §5.3). |
| 6 | Transient memory overhead at most 10% | **Met**: the semantic fit's transient peak is 49–50% lower; peak working set is lower in every phase |
| 7 | No unacceptable in-process refresh memory regression | **Met**: lower peak working set and committed memory than Stage 2 (1.37 vs 1.46 GB; 3.37 vs 3.55 GB) |
| 8 | No SQLite schema change | **Met** (tested) |
| 9 | No new persisted semantic global state | **Met** (tested) |
| 10 | No retrieval behaviour change | **Met** (criterion 1) |
| 11 | Version stays `1.2.0` | **Met** |

## 7. Known limitations

- The semantic index is recomputed in full on every build and refresh; Stage 3 lowers that cost but does not make it
  proportional to the change (§3).
- The single pass over every (document, feature) pair now dominates the fit (§5.4) and grows with the repository.
- The benchmark machine's speed varied widely without paging or suspension (§5.1); the ratios carry that
  uncertainty, and criterion 4 is only partially established at 2,500 files.
- Larger workloads were not measured (§5.7).
- The first build after upgrading re-extracts every semantic artifact once (§5.6).
- The final matrix's dtype depends on SciPy (float64 with SciPy 1.18, float32 with SciPy 1.10), exactly as in Stage 2;
  Stage 3 does not normalise it.
- Local full-suite runs exclude `tests/test_public_api.py` because of a local FastAPI/Starlette incompatibility (also
  at the Stage 2 baseline); CI runs it.

## 8. Deferred work

Stage 4: Tree-sitter and SCIP artifacts, CLI/MCP surfaces and cache commands. Not started. Incremental semantic
maintenance stays rejected unless a future per-document artifact format lets the per-pair pass avoid string hashing
(design §19.1).

## 9. Reproducing

```
git worktree add <dir> 0b273814ba6b31ffa7aa1f13d612057ce0cfa7b9
python reports/v2_completion/persistent_indexing/stage3_benchmark.py --stage2-root <dir> \
    --files 1000 2500 --profile realistic --rounds 3 --verify --upgrade \
    --out reports/v2_completion/persistent_indexing/stage3_benchmark.json
```

## 10. Confirmations

- The semantic index is labelled `recomputed_in_full` everywhere; nothing in Stage 3 is reported as incremental.
- No change to retrieval, ranking weights, score fusion, routing, packing, token budgets or discovery order.
- No cache schema change and no new persisted state; no raw source stored; no new runtime dependency.
- Package version `1.2.0`. No merge, release, tag, PyPI upload, Hugging Face upload or Render deployment. The bundled
  Space copy of the package was re-synchronised locally only.
