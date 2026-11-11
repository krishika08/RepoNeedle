# RepoNeedle Research & Engineering Roadmap

This roadmap is grounded in empirical limitations observed during benchmark evaluations. Status labels distinguish what has been **released**, what is in the **upcoming 1.2.0** release (this repository's current version; PyPI publication pending), and what is **not implemented**.

*Last reconciled with the source code: 2026-11-10.*

---

## Released: RepoNeedle 1.1.0 (PyPI, 2026-11-03)
- [x] Multi-signal hybrid retrieval (field-weighted BM25 + subword semantic vectors + AST repository graph).
- [x] Workflow-adaptive routing (`trace2code`, `code2test`, `edit2ripple`, `comment2context`, `selective`).
- [x] Inverted test-to-target dependency mapping for `code2test` regression test discovery.
- [x] CUD-Pack token-budget packing with multi-tier representations (full files, focus spans, structural skeletons).
- [x] Opt-in `change_impact` ranker (seed-relative relationship scoring).
- [x] CPU-only execution with no GPU or neural-runtime dependencies. Measured mean query latency on real repositories (ARB v2) is ~318 ms; sub-millisecond figures apply only to tiny synthetic corpora.
- [x] Python 3.10, 3.11 and 3.12 (CI matrix).
- [x] Selective abstention heuristic, **always on in 1.1.0**. It is **experimental and uncalibrated**: on the ARB v2 selective split it correctly abstained on **0 of 82** no-gold queries.
- [x] Hugging Face release assets prepared in `hf_artifacts/` (dataset card, Gradio Playground Space bundling the 1.1.0 engine, where abstention is always on).

## Upcoming: RepoNeedle 1.2.0 (PyPI publication pending)
- [x] CLI machine-readable output (`--json`) and anchor files (`--anchors`).
- [x] Native MCP server over STDIO (`reponeedle-mcp`, optional `mcp` extra) with `reponeedle_retrieve`, `reponeedle_change_impact` and `reponeedle_inspect`. Verified with the MCP Python SDK and a raw JSON-RPC STDIO handshake; **not yet validated in a live Claude Code or Cursor session**.
- [x] Experimental abstention made **opt-in (disabled by default)**, with explicit diagnostics (`experimental: true`, `calibrated: false`) on every result.
- [x] Indexing diagnostics: configurable file-size limit (`max_file_size_bytes`, default 500,000 bytes) with recorded skipped and unreadable paths.
- [x] Indexing security: files reached through symlinks (or Windows junctions) that resolve outside the repository root are no longer read; they are recorded in the diagnostics instead.
- [x] Benchmark reproducibility audit: explicit abstention policy per script ([BENCHMARK_CONFIGURATION.md](BENCHMARK_CONFIGURATION.md)).

Test coverage is measured, not assumed: on the pre-release 1.2.0 development branch, line coverage of the `reponeedle` package is **87%** (`pytest --cov=reponeedle`, 2026-11-09). Earlier claims of "100% test coverage" were incorrect.

## Not implemented
| Capability | Status |
| :--- | :--- |
| Persistent / on-disk index cache | Not implemented (the index is rebuilt in memory on every start) |
| Automatic live filesystem updates / file watching | Not implemented (restart the MCP server to refresh) |
| HTTP / SSE MCP transport | Not implemented (STDIO only) |
| AST block slicing (sub-function spans of large files) | Not implemented |
| Calibrated selective retrieval / reliable abstention | Not implemented (open research problem, below) |

---

## Research needed: Reliable Selective Retrieval
The current heuristic (repository vocabulary overlap + $Z$-score peakiness + top-vs-median score margin over the fused ranking scores) does not separate in-scope from out-of-scope queries on real repositories. Its confidence on all 82 ARB v2 no-gold queries ranged from 0.532 to 0.891, far above the engine's default threshold of 0.12.
- [ ] Train and evaluate a dedicated discriminator (e.g. a cross-encoder) on held-out repositories, reporting abstention precision/recall **and** the false-abstention rate on positive queries.
- [ ] Calibrate scores (e.g. temperature or isotonic calibration) and report calibration error before exposing any score as a probability.
- [ ] Keep the heuristic opt-in until a method passes a pre-registered evaluation on ARB v2.
- [ ] Third-party package boundary disambiguation (e.g. `urllib3` vs `requests`) using dependency manifests.

## Phase 2: Multi-Language & Protocol Integration
- [ ] **Tree-sitter & SCIP Indexing**: optional Tree-sitter parsers for TypeScript, Go, Rust, Java and C++; SCIP index ingest for large codebases.
- [ ] **Dynamic Dependency Tracking**: optional pytest / coverage runtime traces to bridge dynamic dispatch and reflection.
- [ ] **Live client validation** of the MCP server in Claude Code, Cursor and Cline, recorded as reproducible integration tests.

## Phase 3: Agent Scaffolding & Scale
- [ ] **Aider Adapter**: drop-in alternative to Aider's RepoMap for workflow routing and test discovery.
- [ ] **Persistent, incremental indexing** (on-disk cache; embedded SQLite/DuckDB backing for monorepos > 100,000 files).
- [ ] **AST block slicing** for monolithic files.
