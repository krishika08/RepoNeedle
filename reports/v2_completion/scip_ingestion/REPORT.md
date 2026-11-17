# V2 Milestone 2B: SCIP Index Ingestion

**Branch:** `feature/v2-scip-ingestion`, from `main` at `0ec9cb7` (includes PR #15, MCP client validation, and PR #16, Tree-sitter extraction).
**Status:** implemented and tested; opt-in; not released. The package version stays 1.2.0, and nothing is published.
**Scope:** RepoNeedle **consumes** SCIP indexes produced by external tools and adds producer-resolved references to its function-level graph. RepoNeedle does not index code, run indexers or build commands, or ship the `scip` CLI.
**User documentation:** [docs/SCIP.md](../../../docs/SCIP.md)

## 0. What this milestone is and is not

| Capability | Status after this milestone |
| :--- | :--- |
| **SCIP ingestion** (reading `index.scip`, validating it against the repository, mapping definitions and references to graph edges) | **Implemented**, opt-in |
| **Tree-sitter syntax extraction** (Milestone 2A) | Unchanged. It composes with SCIP; neither requires the other. |
| **Compiler-backed semantic resolution** | **Not performed by RepoNeedle.** When an index comes from a compiler- or type-checker-backed producer, RepoNeedle *trusts that producer's resolution* after validating paths, ranges and roots. The quality of the edges is bounded by the producer. |
| **Retrieval-quality improvement** | **Not measured and not claimed.** SCIP edges only affect the opt-in `arm101` ranker. No benchmark was rerun and no baseline was changed. |

A successful Protobuf parse is not evidence that symbols were resolved correctly, and correct resolution is not evidence of better retrieval. This report states only what was tested.

## 1. Architecture

```
index.scip ──(size guard)──► ScipIndex.load()          reponeedle/core/scip_ingestion.py
                             official generated bindings  reponeedle/core/_scip/scip_pb2.py
                                │
         repo_root ──► validate_root()   project_root URI vs repository (refuse mismatch by default)
                                │
   indexed documents ──► resolve()        path validation, containment, freshness, range bounds,
                                │          symbol grammar, roles, definitions, references
                                ▼
                         ScipResolution   edges + relationships + definitions + diagnostics
                                │
              FunctionGraphBuilder._apply_scip()  adds `scip_reference` edges (no duplicates)
                                │
                     engine.scip_diagnostics
```

- **Lazy import.** `reponeedle.core.scip_ingestion` imports Protobuf only inside `load_bindings()`, so default installs never import it.
- **Public API.** `ScipConfig` (in `reponeedle.models`, exported from `reponeedle`), the `scip_config=` parameter on `RepoNeedleEngine`, `from_documents` and `from_directory`, and `engine.scip_diagnostics`.
- **Graph changes.**
  - `FunctionGraphEdge` gains `source_symbol`, `target_symbol` and `provenance`, all optional and defaulting to `None`.
  - `FunctionGraphBuilder` gains `scip_index` and `scip_relationships`.
  - `arm101` accepts the new edge type in its allowed set.
- **Unchanged.** Ranking weights, the legacy ranker, CUD-Pack, routing, abstention, MCP tools, CLI, benchmark baselines and the package version.

## 2. Schema and bindings

| Item | Value |
| :--- | :--- |
| Schema source | https://github.com/scip-code/scip, `scip.proto` |
| Revision | tag **v0.10.0**, commit `1c2b6db7e560d5233c944f36e4ac1377cc6963fc` (identical to `main` at `be1d9f7` when checked) |
| `scip.proto` SHA-256 | `b38021b65ef90cbbf6af9c829ff75192859ad9b5da05439ef154bea4ceb2bf03` |
| License | Apache-2.0 (copied to `reponeedle/core/_scip/LICENSE`) |
| Generator | `grpcio-tools` 1.71.0 (`libprotoc` 29.0) → `scip_pb2.py` gencode **5.29.0**, plus `scip_pb2.pyi` |
| Generated files | Checked in **unedited**. `tests/test_scip_parsing.py` pins the proto hash and verifies that the descriptor embedded in `scip_pb2.py` matches the vendored proto. Regeneration commands are in `reponeedle/core/_scip/README.md`. |
| Hand-written decoder | None |

The SCIP repository ships no Python bindings, so vendoring generated code is the reproducible option. Generating at install time would require a protoc toolchain on every machine.

## 3. Dependency: `protobuf`

| Item | Value |
| :--- | :--- |
| Extra | `scip = ["protobuf>=5.29.0,<8"]`. It is **not** a core dependency. |
| Why the lower bound | Gencode 5.29.0 is rejected at import time by older 5.x runtimes (5.28.3 measured: `VersionError`). |
| Why the upper bound | Protobuf's cross-version policy guarantees gencode compatibility only within a bounded window. 6.x and 7.x accept 5.29 gencode (measured); 8.x is unreleased and untested. |
| Runtimes verified locally | 5.29.0, 5.29.5, 6.33.6, 7.36.2 (upb backend) and the pure-Python backend, on Python 3.11 and 3.12 (Windows) |
| Runtimes verified in CI | Linux 3.10/3.11/3.12 with the latest allowed version, 3.10 with exactly 5.29.0, the pure-Python backend, and Windows 3.12 (§8) |
| Wheel metadata | `Requires-Dist: protobuf<8,>=5.29.0; extra == "scip"` |
| Missing dependency | `ScipIngestionError` with `pip install -e ".[scip]"`. `on_error="skip"` builds the engine without SCIP and records the reason. |

## 4. Repository validation (security)

Every check below has a test (`tests/test_scip_security.py` unless noted).

| Threat | Handling |
| :--- | :--- |
| Index for another checkout | `Metadata.project_root` is decoded (`file:///`, `file://localhost`, drive letters, `%3A`, percent-encoding, UNC on Windows) and compared with `realpath`, case-insensitively on Windows. A mismatch or unverifiable root raises unless `allow_project_root_mismatch=True`. The status is recorded either way. |
| Absolute, `..`, `.`, empty-component, NUL and drive paths | The document is rejected with a reason. Nothing is read. |
| Backslash paths | Normalised only when `project_root` is a Windows path (the scip-typescript case); otherwise rejected. |
| Symlink or junction escape | `realpath` containment check. Directory links (or junctions as a fallback) are tested on every platform; the file-symlink test skips where the OS denies symlink creation (Windows without Developer Mode). |
| Document that is a symlink | Rejected, as the SCIP specification requires regular files. |
| Missing or unindexed files | Listed separately in the diagnostics. |
| Case differences | A unique case-insensitive match is accepted on Windows only; on POSIX it is reported as missing. |
| Stale index | `Document.text`, when present, is compared (with CRLF normalised); stale documents are skipped. Otherwise freshness is `unverified`. |
| Bogus ranges | Bounds-checked against the indexed content in the declared encoding. Out-of-bounds occurrences are dropped. |
| Oversized file | `os.stat` size check **before** opening (the test asserts the file is never opened); default 256 MiB. |
| Malformed or unrelated file | `DecodeError` produces an actionable error. A non-empty file with no metadata, documents or symbols is rejected as not a SCIP index. |
| Reading outside the repository | Resolution never opens source files (asserted by patching `open`); it compares against contents RepoNeedle already indexed under the root. |
| Diagnostics leakage | Diagnostics contain paths, counts and producer metadata only; no source text. Lists are capped. |

## 5. Graph semantics

- **Identity.** Symbols are keyed by the exact SCIP symbol string; display names are never used for identity. `local` symbols are keyed by (document, symbol).
- **Edge type.** `scip_reference`, confidence **0.9** (not 1.0), meaning *a reference to a callable defined in another repository file*. Each edge carries `source_symbol`, `target_symbol` and `provenance = "scip:<tool>@<version>"`.
- **Callables.** These come from `SymbolInformation.kind`; the method descriptor suffix is used only when the kind is unspecified.
- **No edges for:**
  - non-callables, external symbols or packages, unresolved symbols;
  - ambiguous symbols (defined in more than one file);
  - definitions in rejected or stale documents;
  - same-file references, `Import` occurrences and forward declarations.
- **Relationships.** These are stored in `function_graph.scip_relationships` and never converted into edges.
- **De-duplication.**
  - One edge per (source path, enclosing symbol, target path, target symbol).
  - An unattributed reference is dropped when an attributed one exists in the same file.
  - An edge that extraction already found (same files and function name) is counted, not duplicated.

## 6. Real producer interoperability

| Producer | Result |
| :--- | :--- |
| **scip-typescript 0.6.2** (TypeScript 5.6.3, Node.js 22, Windows 11) | **VERIFIED as a consumer**: the real, unmodified index is checked in (`tests/fixtures/scip/real/`) and asserted edge-by-edge in `tests/test_scip_graph.py`. |
| scip-python 0.6.8 | **NOT TESTED.** It crashes at startup on Windows (`new RegExp(path.sep)`), so no index could be produced on this host. |
| scip-java, scip-clang, rust-analyzer (SCIP output), scip-go, others | **NOT TESTED** (no toolchain on this host, or out of scope). |

Compatibility with untested producers is expected from the shared schema but is **not** claimed.

### scip-typescript index, through `RepoNeedleEngine.from_directory`

| Measure | Value |
| :--- | :--- |
| Index size | 14,780 bytes; parse 0.48 ms, resolve 11.4 ms |
| Project root | `mismatch` (generated in a neutral directory), accepted only with `allow_project_root_mismatch=True`. Refused without it (tested). |
| Documents | 7 in index, 7 matched; 7 backslash paths normalised; 0 rejected, missing or stale |
| Freshness | `unverified` (scip-typescript does not embed `Document.text`) |
| Position encoding | UTF-16 (7 documents) |
| Occurrences | 153; 0 invalid, 0 out of bounds, 0 malformed symbols |
| Symbols | 63 unique (14 local) |
| Definitions | 55 (15 callable) |
| References | 98:<br>• 26 to repository callables<br>• 44 to repository non-callables<br>• 17 local<br>• 5 same-file<br>• 11 to external packages (TypeScript standard library, not listed in `external_symbols` by the producer)<br>• 0 unresolved or ambiguous |
| Relationships | 4 implementation, 2 reference (stored, not edges) |
| Reference edges | 13 resolved, after 4 unattributed duplicates were dropped |
| Added to the graph | **6**. The other **7** were already found by extraction. |

Resolved edges include `CartView → cart.describe`, `cart.total → format.round`, `tests/cart.test.ts → cart.add / cart.total`, and two distinct `<constructor>` symbols (`Square`, `Circle`) referenced from `tests/shapes.test.ts`. The constructors are kept separate by symbol, not merged by name.

Observed producer deviations, all handled: backslash `relative_path` on Windows; legacy packed ranges only; empty `display_name`; arrow-function constants classified as `Constant`, so they produce no edge; standard-library symbols not declared external. Details are in `tests/fixtures/scip/real/README.md`.

## 7. Tests

| File | Tests | Needs |
| :--- | ---: | :--- |
| `tests/test_scip_core.py` | 56 | nothing (also runs in the strict Linux security job) |
| `tests/test_scip_parsing.py` | 31 | `scip` |
| `tests/test_scip_security.py` | 27 | `scip` |
| `tests/test_scip_graph.py` | 23 test functions (more cases with parametrisation) | `scip` |
| `tests/test_scip_tree_sitter.py` | 6 | `scip` + `treesitter` |

Test indexes are generated with the vendored official bindings (`tests/scip_support.py`), so they are real Protobuf messages, not hand-encoded bytes.

**Local results** (Windows 11, 2026-11-17):

| Environment | Result |
| :--- | :--- |
| Full suite, Python 3.12.10, `treesitter` + protobuf 7.36.2 | **835 passed, 8 skipped**. All skips are file-symlink creation denied by Windows: 6 in indexing security, 1 MCP, 1 SCIP. |
| Full suite, Python 3.11.9, **no extras** | **630 passed, 13 skipped**. The skips are the symlink tests plus the optional-extra modules. |
| SCIP + Tree-sitter suites, protobuf **5.29.0** | 179 passed, 1 skipped (symlink) |
| Same, protobuf 6.33.6 | 179 passed, 1 skipped |
| Same, pure-Python Protobuf backend | 179 passed, 1 skipped |
| Existing Tree-sitter, FunctionGraph and 1.2.0 golden tests | Included in the full-suite runs above; no changes needed |
| `git diff --check` | clean |

**Install checks** (`install_smoke.py`, against built wheels):
- **Base wheel with no extras:** Protobuf is absent, SCIP fails with install instructions, `on_error="skip"` works, and the default engine is unchanged.
- **`[scip]` only:** the real index is ingested.
- **`[scip,treesitter]`:** the real index is ingested.

Wheel and sdist both build, `twine check --strict` passes, the wheel contains `_scip/` with `scip.proto`, `LICENSE`, `README.md` and `.pyi`, and the test fixtures are not packaged.

## 8. CI

New `scip-optional` job:
- Linux, Python 3.10, 3.11 and 3.12 with `[scip]`;
- Linux 3.10 pinned to `protobuf==5.29.0`;
- Linux 3.11 with the pure-Python backend;
- Linux 3.12 with `[scip,treesitter]` (adds the composition and Tree-sitter graph suites);
- Windows 3.12.

Linux legs fail on any skip (`REPONEEDLE_FAIL_ON_SKIP`); Windows allows the symlink skip. The wheel-install job now checks:
- that a base install contains **no** Protobuf;
- the SCIP-absent smoke;
- `[scip]` only;
- `[scip,treesitter]`.

The strict Linux security job also runs `test_scip_core.py`. The workflow passes `actionlint`. CI results for the pull request are recorded in the PR description.

## 9. Performance

Synthetic indexes: 20 functions per file and 40 occurrences per file, half of them cross-file references. Measured with `bench_scip.py` on Windows 11, Python 3.12.10, protobuf 7.36.2 (upb), one fresh interpreter per size, median of 3. Raw data is in `benchmark_results.json`.

| Documents | Occurrences | Index | Parse | Resolve (cold) | Resolve (repeated) | Graph build without / with SCIP | Peak Python allocations |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 400 | 27 KB | 0.5 ms | 9.9 ms | 8.8 ms | 2.6 / 14.2 ms | 0.4 MB |
| 100 | 4,000 | 281 KB | 1.7 ms | 79 ms | 111 ms | 29 / 117 ms | 4.8 MB |
| 1,000 | 40,000 | 2.9 MB | 12 ms | 0.94 s | 2.8 s | 0.71 / 3.6 s | 48 MB |
| 5,000 | 200,000 | 15.4 MB | 100 ms | 12.8 s | 13.1 s | 3.6 / 18.2 s | 240 MB (RSS ≈ 1 GB) |

**Caveats:**
- The host had about 3 GB of free RAM during measurement, and timings varied by up to 3× between runs at 1,000 documents.
- Per-occurrence cost rose from about 22 µs to 65–70 µs at scale, which points to memory pressure or cache effects rather than an algorithmic term (resolution is a fixed number of dictionary passes). This was not confirmed on another machine.
- Synthetic "graph edges added" is 0 because regex extraction already finds these unique-name calls, which is itself a confirmation of de-duplication.
- **Size guard:** `max_index_bytes`, default 256 MiB, is checked with `os.stat` before reading. For very large monorepos the bottleneck is resolution time, not the guard.

## 10. Limitations

1. Only one real producer (scip-typescript, on Windows) was validated. Linux-generated real indexes were not tested; synthetic indexes cover the canonical `/` path form.
2. A `scip_reference` edge means "references a callable", not "calls". SCIP has no call role.
3. Edge quality depends entirely on the producer's resolution and symbol kinds.
4. Freshness is provable only when `Document.text` is embedded, which scip-typescript does not do. Root matching and range bounds catch some, but not all, stale indexes.
5. One index per engine. There is no merging, no cross-repository resolution, and no persistent cache; `update_documents()` re-resolves the whole index.
6. Resolution is single-threaded Python. Large indexes (hundreds of thousands of occurrences) take seconds to tens of seconds (§9).
7. The bindings target Protobuf 5.29–7.x. Protobuf 8 will need regeneration and a new test.
8. Not exposed through the MCP server or the CLI.
9. No retrieval-quality evaluation was performed with SCIP edges.

## 11. Reproducing

```bash
pip install -e ".[scip,treesitter]" pytest
pytest tests/test_scip_core.py tests/test_scip_parsing.py tests/test_scip_security.py tests/test_scip_graph.py tests/test_scip_tree_sitter.py
python reports/v2_completion/scip_ingestion/bench_scip.py
python -m build && pip install "dist/reponeedle-1.2.0-py3-none-any.whl[scip]"
python reports/v2_completion/scip_ingestion/install_smoke.py present .
```
