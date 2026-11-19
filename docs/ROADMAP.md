# RepoNeedle Research & Engineering Roadmap

This roadmap is grounded in empirical limitations observed during benchmark evaluations. Status labels distinguish what has been **released** (1.1.0 and 1.2.0) and what is **not implemented**.

*Last reconciled with the source code: 2026-11-18.*

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

## Released: RepoNeedle 1.2.0 (PyPI, 2026-11-12)
- [x] CLI machine-readable output (`--json`) and anchor files (`--anchors`).
- [x] Native MCP server over STDIO (`reponeedle-mcp`, optional `mcp` extra) with `reponeedle_retrieve`, `reponeedle_change_impact` and `reponeedle_inspect`. Verified with the MCP Python SDK and a raw JSON-RPC STDIO handshake. Live clients were validated after the release (see Phase 2): **Claude Code verified; Cursor and Cline not tested**.
- [x] Experimental abstention made **opt-in (disabled by default)**, with explicit diagnostics (`experimental: true`, `calibrated: false`) on every result.
- [x] Indexing diagnostics: configurable file-size limit (`max_file_size_bytes`, default 500,000 bytes) with recorded skipped and unreadable paths.
- [x] Indexing security: files reached through symlinks (or Windows junctions) that resolve outside the repository root are no longer read; they are recorded in the diagnostics instead.
- [x] Benchmark reproducibility audit: explicit abstention policy per script ([BENCHMARK_CONFIGURATION.md](BENCHMARK_CONFIGURATION.md)).

Test coverage is measured, not assumed: on the pre-release 1.2.0 development branch, line coverage of the `reponeedle` package is **87%** (`pytest --cov=reponeedle`, 2026-11-09). Earlier claims of "100% test coverage" were incorrect.

## Not implemented
| Capability | Status |
| :--- | :--- |
| Incremental index maintenance | Partial, opt-in, unreleased. With the persistent cache (Stages 1–2), graph call and import resolution is limited to affected files and BM25 bookkeeping is partially incremental for in-process `refresh()`; the semantic index, PageRank and other global graph quantities are recomputed in full, and `update_documents()`/`remove_documents()` still refit every index in memory. Stages 3–4: [PERSISTENT_INDEXING_DESIGN.md](PERSISTENT_INDEXING_DESIGN.md) |
| Automatic live filesystem updates / file watching | Not implemented (restart the MCP server to refresh) |
| HTTP / SSE MCP transport | Not implemented (STDIO only) |
| AST block slicing (sub-function spans of large files) | Opt-in on `main`, not released ([AST_BLOCK_SLICING.md](AST_BLOCK_SLICING.md)) |
| Calibrated selective retrieval / reliable abstention | Not implemented (open research problem, below) |

---

## Research needed: Reliable Selective Retrieval
The current heuristic (repository vocabulary overlap + $Z$-score peakiness + top-vs-median score margin over the fused ranking scores) does not separate in-scope from out-of-scope queries on real repositories. Its confidence on all 82 ARB v2 no-gold queries ranged from 0.532 to 0.891, far above the engine's default threshold of 0.12.
- [ ] Train and evaluate a dedicated discriminator (e.g. a cross-encoder) on held-out repositories, reporting abstention precision/recall **and** the false-abstention rate on positive queries.
- [ ] Calibrate scores (e.g. temperature or isotonic calibration) and report calibration error before exposing any score as a probability.
- [ ] Keep the heuristic opt-in until a method passes a pre-registered evaluation on ARB v2.
- [ ] Third-party package boundary disambiguation (e.g. `urllib3` vs `requests`) using dependency manifests.

## Phase 2: Multi-Language & Protocol Integration
- [x] **Tree-sitter structural extraction** (opt-in, optional `treesitter` extra; on `main`, not in a published release yet): syntax-tree extraction of functions, methods, imports and call sites for TypeScript/TSX, Go, Rust, Java and C++ in the function-level call graph, with per-file fallback to the regex extractor. Syntax-aware only, not semantic code intelligence; it affects only the opt-in `arm101` ranker, and no retrieval improvement has been measured. See [TREE_SITTER.md](TREE_SITTER.md).
- [x] **SCIP index ingestion** (opt-in, optional `scip` extra; on `main`, not in a published release yet): consumes `index.scip` files produced by external indexers and adds producer-resolved references to callables as `scip_reference` edges, with repository-root, path and freshness validation. It is a SCIP consumer, not an indexer. Only scip-typescript has been validated with a real index, it affects only the opt-in `arm101` ranker, and no retrieval improvement has been measured. See [SCIP.md](SCIP.md).
- [ ] **Dynamic Dependency Tracking**: optional pytest / coverage runtime traces to bridge dynamic dispatch and reflection.
- **Live client validation** of the MCP server (V2 Milestone 1; [validation report](../reports/v2_completion/mcp_client_validation/REPORT.md), [MCP_INTEGRATION.md](MCP_INTEGRATION.md)):
  - [x] **Claude Code 2.1.81: verified** (PR #15, 2026-11-16) on Windows 11 over STDIO, in non-interactive (`-p`) sessions. Claude Code discovered and called all three tools and used the results in a coding workflow. Interactive sessions and macOS/Linux were not tested.
  - [ ] **Cursor: not tested.** Cursor 2.6.20 was installed, but no RepoNeedle tool was called from it.
  - [ ] **Cline: not tested** (not installed on the validation host).
  - [ ] Recording client sessions as reproducible integration tests.

## Phase 3: Agent Scaffolding & Scale
- [ ] **Aider Adapter**: drop-in alternative to Aider's RepoMap for workflow routing and test discovery.
- **Persistent, incremental indexing** (opt-in on-disk cache for large repositories):
  - [x] **Design** (Milestone 4A, design only, revised after an architecture review): SQLite (standard library) storage of self-contained, checksummed per-file artifacts with no raw source; fingerprints including discovery metadata; a writer connection protocol and a single-transaction publish; dependency-scoped invalidation; a security and privacy model; an exact-equivalence acceptance harness; a staged plan; and decisions on all eight open questions. See [PERSISTENT_INDEXING_DESIGN.md](PERSISTENT_INDEXING_DESIGN.md) and the [architecture report](../reports/v2_completion/persistent_indexing/ARCHITECTURE_REPORT.md). Database sizes come from an isolated research prototype; the size limits are provisional.
  - [x] **Stage 0: correctness prerequisites** (not in a published release): function-graph rebuilds no longer keep state from earlier document collections; per-document cache signatures are SHA-256 based and identical across processes; `RepoNeedleEngine.remove_documents()` removes documents in memory and refits; a differential equivalence harness with a frozen 225-query corpus and a mutation suite compares lifecycles with fresh builds. No persistence. See the [Stage 0 report](../reports/v2_completion/persistent_indexing/STAGE0_REPORT.md).
  - [x] **Stage 1: opt-in persistent index cache** (not in a published release): `from_directory(..., index_cache=IndexCacheConfig(...))` stores verified per-file artifacts in SQLite and reuses them on later starts; `engine.refresh()` publishes a new generation. Global structures are recomputed in full on every start, so this is persistence, not incremental indexing; results are identical to an uncached build. Tree-sitter and SCIP configurations are not persisted yet. See the [Stage 1 report](../reports/v2_completion/persistent_indexing/STAGE1_REPORT.md).
  - [x] **Stage 2: dependency-scoped re-resolution and incremental bookkeeping** (not in a published release): typed provider/consumer keys for both graphs; only affected files are re-resolved and every other file's verified edges are replayed in discovery order; PageRank and other global graph quantities are recomputed in full; BM25 is partially incremental for in-process `refresh()`; abstainer reference counts; stable file ids (schema version 2, migrated in place); eviction leases and pending-purge reporting. The default resolvers use lookup indexes in every build. See the [Stage 2 report](../reports/v2_completion/persistent_indexing/STAGE2_REPORT.md).
  - [ ] Stages 2–4: incremental global maintenance (BM25 bookkeeping, graphs, then semantic), optional components, CLI/MCP surfaces. **Not started.**
- [x] **AST block slicing** for monolithic files (opt-in `BudgetConfig(focus_span_strategy="ast_blocks")`; on `main`, not in a published release yet): CUD-Pack focus spans become the smallest complete functions, methods or declarations containing query matches, with relevant imports and enclosing class headers. Python uses `ast`; TypeScript/TSX, Go, Rust, Java and C++ use the optional Tree-sitter extra. Every other case falls back to the unchanged legacy extractor. The default packing is unchanged. In a packing-level comparison on frozen candidate lists, complete blocks cost more tokens per file, so compact mode packed fewer files. No retrieval improvement is claimed. See [AST_BLOCK_SLICING.md](AST_BLOCK_SLICING.md).
