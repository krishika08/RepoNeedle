# Changelog

All notable changes to RepoNeedle are documented here. Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Optional Tree-sitter structural extraction** for the function-level call graph (opt-in with `AblationConfig(structural_parser="tree_sitter")`, optional `treesitter` extra). It covers TypeScript/TSX, Go, Rust, Java and C++, and extracts functions, methods with their containers, imports and call sites, with exact line numbers. Python keeps its `ast` extractor.
  - Import-bound calls are resolved through their imports only; external or unresolvable imports produce no edge.
  - Each file falls back to the existing regex extractor when its parser is unavailable, with the reason recorded in `function_graph.diagnostics["structural_parser"]`.
  - It is syntax-aware extraction, not semantic analysis. It affects only the opt-in `arm101` ranker, and **no retrieval-quality improvement is claimed or measured**. See [docs/TREE_SITTER.md](docs/TREE_SITTER.md) and `reports/v2_completion/tree_sitter/REPORT.md`.
- `CallSite.qualifier_path` (optional, default `None`): the full call qualifier, set by the Tree-sitter extractor only.
- **Optional SCIP index ingestion** (opt-in with `scip_config=ScipConfig(index_path=...)` on `from_directory`, `from_documents` or the engine constructor; optional `scip` extra, `protobuf>=5.29.0,<8`). It reads an `index.scip` produced by an external indexer using the official SCIP schema (v0.10.0, vendored generated bindings).
  - It validates the index's `project_root`, every document path (canonical form, containment, symlinks), freshness (when `Document.text` is present) and every occurrence range against the repository.
  - References to callables defined in another repository file become `scip_reference` edges (confidence 0.9, with SCIP symbol identifiers and producer provenance). Implementation and type-definition relationships are stored separately and are never converted into call edges.
  - `engine.scip_diagnostics` reports the producer, root match, document and reference outcomes, and timings.
  - It is a SCIP consumer, not an indexer. Only scip-typescript 0.6.2 was validated with a real index. It affects only the opt-in `arm101` ranker (which now also propagates over `scip_reference` edges), and **no retrieval-quality improvement is claimed or measured**. See [docs/SCIP.md](docs/SCIP.md) and `reports/v2_completion/scip_ingestion/REPORT.md`.
- `FunctionGraphEdge.source_symbol`, `target_symbol` and `provenance` (optional, default `None`): set on SCIP-derived edges only.
- **Optional AST block slicing** for CUD-Pack focus spans (opt-in with `BudgetConfig(focus_span_strategy="ast_blocks")`; the default `"legacy"` is unchanged).
  - It renders the smallest complete function, method, nested function or declaration containing each query match, instead of line windows. Decorators, attributes, annotations and attached doc comments are included, along with relevant imports, package declarations and the headers of enclosing classes and functions. Elided line ranges are marked explicitly.
  - Python uses `ast` (no extra). TypeScript/TSX, Go, Rust, Java and C++ use the optional `treesitter` extra, sharing the existing parser cache through the new `tree_sitter_extraction.parse_source()`.
  - Blocks are never cut: an oversized block is shown as its signature, or the file falls back. Unsupported languages (including JavaScript and C), missing parsers, any syntax error and unmatched queries fall back per file to the legacy extractor. The CUD-Pack tiers, exact token accounting and the budget invariant are unchanged.
  - Caching: the parsed-structure and result caches are keyed by a SHA-256 digest of the content (never the content itself) and are LRUs bounded by entry count and by an estimated retained-byte budget (32 MiB and 16 MiB by default; configurable). Entries over one eighth of a budget are not cached, and `CodeSpanExtractor.block_cache_stats()` reports the state. The byte figures are estimates, not process memory.
  - `extract_block_span(..., cap_lines=None)`: `cap_lines` is a soft selection budget that never truncates a block (the best block is always rendered whole). It is also passed to the legacy fallback, and it is part of the cache key.
  - New: `reponeedle.core.block_slicing`, `reponeedle.core.bounded_cache`, `CodeSpanExtractor.extract_block_span()`, `CodeSpanExtractor.slice_blocks()` and `CodeSpanExtractor.block_cache_stats()`. **No retrieval-quality improvement is claimed or measured.** In a packing-level comparison, complete blocks used more tokens per file, so compact packs held fewer files. See [docs/AST_BLOCK_SLICING.md](docs/AST_BLOCK_SLICING.md) and `reports/v2_completion/ast_block_slicing/REPORT.md`.

- **`RepoNeedleEngine.remove_documents(paths)`** (V2 Stage 0): removes documents by exact repository-relative path, in memory (no document file is read; with an opt-in SCIP index the refit re-validates SCIP document paths on disk, like any build), and refits every index over the remaining documents in their existing order. The result equals a fresh build over those documents. It returns the removed paths in index order. Duplicates in the request are removed once; an empty request changes nothing. A single string or a non-string path raises `TypeError`. An unknown or already removed path raises `KeyError` before anything changes. It is not transactional: if the refit raises, the previous documents are refitted before the error propagates.

### Fixed

- **Function-graph rebuilds kept state from earlier document collections** (V2 Stage 0). `FunctionGraphEngine.build_graph()` did not clear `module_to_path` or `package_to_files`, so rebuilding on a smaller document set could resolve calls to files no longer indexed. It also kept Tree-sitter/SCIP diagnostics and SCIP relationships from an earlier build. Every build-derived structure is now reset per build; the per-document extraction caches are kept. Not reachable through the 1.2.0 engine, which never removed documents.
- **`BM25Index.fit([])` and `SubwordSemanticIndex.fit([])` kept the previous fit's arrays, IDF and vocabulary.** An empty fit now leaves the same state as a never-fitted index.
- **Per-document cache signatures** (BM25 terms, semantic features, abstainer vocabulary, function-graph and Tree-sitter extractions) used Python's per-process-randomised `hash()` and joined symbols with `,` (so `["a,b"]` and `["a", "b"]` collided). They are now SHA-256 over type- and length-framed extractor inputs plus a versioned namespace (`reponeedle.core.signatures`), identical across processes. Extraction results are unchanged.

### Not changed

- V2 Stage 0 adds no persistence: no SQLite, index cache or `IndexCacheConfig`. Retrieval scores, rankings, routing, packing and defaults are unchanged; the differential equivalence harness (`tests/index_equivalence.py`) checks the lifecycle operations against fresh builds.
- The default extraction (`structural_parser="regex"`) reproduces 1.2.0 exactly; this is checked against a golden snapshot of the 1.2.0 implementation. Without `scip_config` no SCIP code or Protobuf import runs. With the default `focus_span_strategy="legacy"`, focus spans, skeletons and packs are identical to the baseline packer (checked against a golden snapshot). Ranking weights, routing, packing, abstention defaults, the MCP tools and the core dependencies are unchanged.

## [1.2.0] — 2026-11-12

### Highlights

- **Native MCP server** (`reponeedle-mcp`, optional `mcp` extra) for MCP-capable coding agents over STDIO.
- **Machine-readable CLI output** (`--json`) and **anchor files** (`--anchors`).
- **Indexing security**: files reached through links that resolve outside the repository are no longer read.
- **Indexing diagnostics** and a configurable file-size limit.
- **Behaviour change**: the experimental selective-abstention heuristic is now **disabled by default**.

This release does **not** change retrieval quality. No ranking algorithm, fusion weight, task routing or packing default was changed, and no retrieval improvement is claimed. See [Not changed](#not-changed-in-120).

### Added

#### MCP server (optional `mcp` extra)
- Install: `pip install "reponeedle[mcp]"`. Run: `reponeedle-mcp --repo /path/to/project` (or `python -m reponeedle.mcp`).
- Tools:
  - `reponeedle_retrieve`: context retrieval within a token budget. Optional `enable_experimental_abstention`, default `false`.
  - `reponeedle_change_impact`: files and tests related to modified anchor files.
  - `reponeedle_inspect`: index metadata, indexing diagnostics and abstention status.
- The repository is indexed once at startup; restart the server to pick up changes. Path arguments are confined to the repository root.
- `serverInfo.version` reports RepoNeedle's version.
- STDIO transport only. Tested with the MCP Python SDK and a JSON-RPC STDIO session. It has **not** been validated in a live session of any specific coding client (Claude Code, Cursor, Cline, Windsurf); configuration examples follow each client's documented format.
- Without the extra, the core package is unaffected, and `reponeedle-mcp` prints installation instructions.

#### CLI
- `--json`: emits a single JSON document on stdout (`schema_version` `1.2.0`). It contains selected files, scores, tiers, token counts, and `abstention` and `indexing` objects. Diagnostics go to stderr only.
- `--include-context`: includes the rendered prompt context in the JSON output.
- `--anchors PATH [PATH ...]`: seed (anchor) files for change-impact and ripple queries. Paths are validated and must stay inside the repository. Windows-style paths (`src\app.py`) are accepted on Linux and macOS.
- `--enable-experimental-abstention`: opts in to the experimental abstention heuristic.
- `--max-file-size-bytes BYTES`: per-file indexing limit (default 500,000).

#### Python API
- `RepoNeedleEngine.retrieve(..., anchor_files=[...])` and `Query(anchor_files=[...])`.
- `RepoNeedleEngine.from_directory(..., max_file_size_bytes=500_000)`. A zero, negative or non-integer limit raises an error.
- `engine.indexing_diagnostics` (`IndexingDiagnostics`) reports:
  - the number of indexed files;
  - skipped oversized files (paths only);
  - unreadable files;
  - links resolving outside the repository;
  - directory links and junctions that were not traversed;
  - whether the `max_files` cap was reached.
- `RetrievalResult.abstention` (`AbstentionDiagnostics`): whether the heuristic was applied, with `experimental: true` and `calibrated: false`.
- `BudgetConfig.enable_experimental_abstention` and `retrieve(..., enable_experimental_abstention=...)`.
- New exports: `AbstentionDiagnostics`, `IndexingDiagnostics`, `DEFAULT_MAX_FILE_SIZE_BYTES`.

### Changed

- **Experimental abstention is off by default.** In 1.1.x every query could abstain on heuristic grounds. The heuristic is uncalibrated: it correctly abstained on 0 of 82 no-gold queries in the ARB v2 selective split. In 1.2.0, out-of-scope queries return ranked results unless you opt in (see [Migration](#migrating-from-11x)).
  - `task_type="selective"` does not enable it.
  - Empty repositories still return `abstained=True`.
  - `confidence_score` is still reported. It remains an uncalibrated diagnostic, not a probability.
- **Skipped files are reported.** A `WARNING` is logged on the `reponeedle.engine` logger (stderr by default) when files are skipped, and details are recorded in `indexing_diagnostics`. Files are skipped when they:
  - exceed the size limit;
  - are unreadable;
  - resolve outside the repository;
  - fall beyond the `max_files` cap.

  The warning and diagnostics contain repository-relative paths and counts only, never file contents.

### Security

- **Indexing no longer reads files outside the repository through links.** `from_directory` resolves every file before opening it. Files whose canonical location is outside the repository root (symlinks, and junctions on Windows) are skipped without reading the target. Each skipped link is listed by its in-repository path in `indexing_diagnostics.symlink_outside_repository_paths` (reason `symlink_outside_repository`).
  - In 1.1.0 such files were indexed, and their contents could be returned by retrieval, including through any tool built on it.
  - Links resolving inside the repository are still indexed.
- **Directory links are never traversed, and traversal is bounded.** Directory symlinks and Windows junctions are not followed on any platform, and no physical directory is entered twice. In 1.1.0, Windows junctions were followed (`os.path.islink` is False for them): a junction to an ancestor directory caused repeated traversal and duplicate index entries until the path length limit, and a junction to an outside directory caused its listings to be traversed. Skipped directories are recorded by in-repository path only (`skipped_directory_paths`, `skipped_directories_outside_repository`), with a count-only warning for those resolving outside the repository. Files under an in-repository link target are indexed once, under their real path. A directory reachable **only** through a directory link (for example a link or junction to a sibling checkout, or to a directory excluded by ignore rules) is therefore not indexed. On Windows this is a change from 1.1.0; on Linux and macOS directory symlinks were already not followed.
- CLI anchors use the same canonical containment check: an anchor that links outside the repository is rejected.

### Fixed

- Anchor and MCP path validation now check whole path components. Legitimate names beginning with `..` (for example `..cache/x.py`) are accepted; real parent-directory traversal is still rejected.
- CLI anchors written with backslashes (`src\app.py`) are accepted on Linux and macOS, consistent with `retrieve(anchor_files=...)`. The exact spelling is tried first. Traversal such as `..\outside.py` is still rejected.
- The MCP server reports RepoNeedle's version in `serverInfo.version`, instead of the MCP SDK's.

### Optional extras

| Extra | Installs | Purpose |
| :--- | :--- | :--- |
| `mcp` | `mcp>=1.28,<2` | MCP server (`reponeedle-mcp`) |
| `api` | `fastapi`, `httpx`, `uvicorn` | Dependencies for the repository's demonstration HTTP API (`api.py`). Present since 1.1.0. No module inside the `reponeedle` package imports them. |
| `dev` | `pytest`, `pytest-cov`, `pytest-asyncio` | Test tooling. `pytest-asyncio` is new in 1.2.0. |
| `hf` | `huggingface_hub`, `gradio` | Hugging Face release tooling (unchanged) |

The core runtime dependencies are unchanged from 1.1.0: `numpy`, `scipy`, `networkx`, `pydantic`, `pathspec`, `rich`, and `tomli` on Python < 3.11. Python 3.10, 3.11 and 3.12 are supported.

### Backward compatibility

- All 1.1.0 public call signatures, `RetrievalResult` fields and CLI options keep working. New parameters are optional keywords, and new result fields are additions.
- The default ranker (`legacy`) and all ranking, fusion, routing and packing defaults are unchanged. On every ARB v2 query compared (82 selective and 53 positive), the pre-release development branch produced rankings bit-identical to 1.1.0. Later changes in 1.2.0 do not touch the ranking path; they were not re-measured.
- `change_impact` results for `AUTO` queries report the router-classified task, as in 1.1.0. This is now covered by regression tests.
- Behaviour differs from 1.1.0 in four places:
  - abstention is off by default;
  - links resolving outside the repository are no longer indexed;
  - directory links and Windows junctions are not traversed (on Linux and macOS this was already the case);
  - skipped files produce a logged warning.

### Migrating from 1.1.x

- **Restore the 1.1.x abstention behaviour:**
  - Python, engine-wide: `RepoNeedleEngine.from_directory(path, budget_config=BudgetConfig(enable_experimental_abstention=True))`
  - Python, per call: `engine.retrieve(..., enable_experimental_abstention=True)`
  - CLI: `--enable-experimental-abstention`
  - MCP: `"enable_experimental_abstention": true`
- **If you relied on indexing files through links that point outside the repository** (file links, directory symlinks or Windows junctions): move or copy those files into the repository, or point `--repo` / `from_directory` at the directory that actually contains them. Check `engine.indexing_diagnostics.symlink_outside_repository_paths` and `skipped_directory_paths` to see what was skipped.
- **If large files are skipped:** raise the limit with `max_file_size_bytes` (Python) or `--max-file-size-bytes` (CLI and MCP).
- **If the new indexing warning is unwanted:** adjust the `reponeedle.engine` logger level with the standard `logging` configuration.

### Development and CI

- New Linux CI job (`mcp-security-linux`): installs `.[dev,mcp]` and runs the MCP, link-security and compatibility suites. Skipped tests fail the job (`REPONEEDLE_FAIL_ON_SKIP=1`). It also runs a live MCP STDIO start-up check.
- Release workflow, before publishing:
  1. A `validate` job checks that the tag, `pyproject.toml` and `reponeedle.__version__` agree. It then runs the full test suite and the strict MCP/security suites.
  2. `build` runs after `validate` and checks the built artifact versions.
  3. `publish` runs only after both succeed. It is the only job with publishing (OIDC) permission.

### Documentation and evaluation

- README restructured with a quickstart, a release-status table and a clear separation of benchmark kinds.
- Historical ARB v2 results remain as published, labelled with their engine provenance (commit `8e00425`, 2026-10-28).
- Current-engine official-harness results, a supplemental whole-file evaluation, and experimental studies are reported separately (`docs/BENCHMARK_CONFIGURATION.md`, `reports/experimental/`). Supplemental and experimental results are **not** official ARB scores.
- Corrected earlier inaccurate claims:
  - synthetic "100% abstention accuracy";
  - "calibrated abstention";
  - "100% test coverage";
  - abstention threshold and score ranges;
  - the `comment2context` root-cause analysis.

### Not changed in 1.2.0

- **Documentation filtering** (`enable_doc_filter`) remains **disabled by default**. A pre-registered held-out validation did **not** validate it.
- **Lexical retrieval** is unchanged. The investigated lexical optimisations were **not validated**, and none was adopted.
- The Hugging Face Space and the demonstration API (`api.py`) still bundle the 1.1.0 engine. They are updated separately.

### Known limitations

- The abstention heuristic is experimental and uncalibrated. Out-of-scope queries are not detected by default.
- `comment2context` deep recall remains below BM25 on matched whole-file input (supplemental evaluation: Recall@20 −0.090, repository-clustered 95% CI [−0.178, −0.006]).
- Automatic task routing (`AUTO`) agrees with ARB task labels on 36% of queries. Benchmark results pass task labels explicitly.
- Not implemented: a persistent index cache, live filesystem updates, HTTP/SSE MCP transport, and AST block slicing of large files.
- The MCP server indexes once at startup, and `skipped_paths` is unbounded.

See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for details.

## [1.1.0] — 2026-11-03

Opt-in `change_impact` ranker (seed-relative change-impact retrieval). See [docs/v1.1_change_impact_release.md](docs/v1.1_change_impact_release.md).
