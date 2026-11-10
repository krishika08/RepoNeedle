# RepoNeedle 1.2.0 — Proposed Changelog (draft, not yet released)

## Highlights

- **Native MCP server** (`reponeedle-mcp`, optional `mcp` extra) for MCP-capable coding agents over STDIO.
- **Machine-readable CLI output** (`--json`) and **anchor files** (`--anchors`).
- **Indexing diagnostics** and a configurable file-size limit.
- **Behaviour change**: the experimental selective-abstention heuristic is now **disabled by default**.

## New features

### MCP server (optional)
- Install: `pip install "reponeedle[mcp]"`. Run: `reponeedle-mcp --repo /path/to/project` (or `python -m reponeedle.mcp`).
- Tools: `reponeedle_retrieve` (context retrieval within a token budget; optional `enable_experimental_abstention`, default `false`), `reponeedle_change_impact` (files and tests related to modified anchor files), `reponeedle_inspect` (index metadata, indexing diagnostics, abstention status).
- The repository is indexed once at startup; restart the server to refresh. Path arguments are confined to the repository root.
- STDIO transport only. Tested with the MCP Python SDK and a JSON-RPC STDIO session; not yet validated in a live Claude Code or Cursor session.
- Without the extra, the core package is unaffected and `reponeedle-mcp` prints installation instructions.

### CLI
- `--json`: emits one JSON document on stdout (`schema_version` 1.2.0) with selected files, scores, tiers, token counts, `abstention` and `indexing` objects. Diagnostics go to stderr only.
- `--include-context`: include the rendered prompt context in the JSON output.
- `--anchors PATH [PATH ...]`: seed/anchor files for change-impact and ripple queries; paths are validated and must stay inside the repository.
- `--enable-experimental-abstention`: opt in to the experimental abstention heuristic.
- `--max-file-size-bytes BYTES`: per-file indexing limit (default 500,000).

### Python API
- `RepoNeedleEngine.retrieve(..., anchor_files=[...])` and `Query(anchor_files=[...])`.
- `RepoNeedleEngine.from_directory(..., max_file_size_bytes=500_000)`; invalid (zero, negative, non-integer) limits raise.
- `engine.indexing_diagnostics` (`IndexingDiagnostics`): indexed files, skipped oversized files (paths only), unreadable files, `max_files` cap reached.
- `RetrievalResult.abstention` (`AbstentionDiagnostics`): whether the heuristic was applied, with `experimental: true` and `calibrated: false`.
- `BudgetConfig.enable_experimental_abstention` and `retrieve(..., enable_experimental_abstention=...)`.
- New exports: `AbstentionDiagnostics`, `IndexingDiagnostics`, `DEFAULT_MAX_FILE_SIZE_BYTES`.

## Behaviour changes and migration

- **Experimental abstention is off by default.** In 1.1.x every query could abstain on heuristic grounds; the heuristic is uncalibrated (0 of 82 correct abstentions on the ARB v2 selective split). In 1.2.0, out-of-scope queries return ranked results unless you opt in:
  - Python: `BudgetConfig(enable_experimental_abstention=True)` or `retrieve(..., enable_experimental_abstention=True)`
  - CLI: `--enable-experimental-abstention`
  - MCP: `"enable_experimental_abstention": true`

  `task_type="selective"` does not enable it. Empty repositories still return `abstained=True`. `confidence_score` is still reported and remains an uncalibrated diagnostic, not a probability.
- **Skipped files are reported.** When files exceed the size limit, are unreadable, or the `max_files` cap is hit, a `WARNING` is logged on the `reponeedle.engine` logger (stderr by default) and details are recorded in `indexing_diagnostics`.
- **`api` extra retained.** The optional `api` extra published with 1.1.0 (`fastapi`, `httpx`, `uvicorn`) is kept so `pip install "reponeedle[api]"` continues to work. It remains optional, and no RepoNeedle module imports these packages.

## Security
- **Indexing no longer reads files outside the repository through links.** `from_directory` resolves every file before opening it and skips files whose canonical location is outside the repository root (symlinks; junctions on Windows), without reading the target. Skipped links are listed by their in-repository path in `indexing_diagnostics.symlink_outside_repository_paths` (reason `symlink_outside_repository`). In 1.1.0 such files were indexed and their contents could be returned by retrieval. Links resolving inside the repository are still indexed.
- CLI anchors use the same canonical containment check, so an anchor that links outside the repository is rejected.

## Fixes
- `change_impact` results report the router-classified task for `AUTO` queries, restoring the behaviour of the published 1.1.0 wheel (reporting only; ranking unchanged).
- Anchor and MCP path validation are now component-aware: legitimate names beginning with `..` (e.g. `..cache/x.py`) are accepted, and real parent traversal is still rejected.
- The MCP server reports RepoNeedle's version in `serverInfo.version` (previously the MCP SDK's version).

## Development and CI
- `pytest-asyncio` added to the `dev` extra.
- New Linux CI job installs `.[dev,mcp]` and runs the MCP and symlink-security suites with skips treated as failures (`REPONEEDLE_FAIL_ON_SKIP=1`).
- Release workflow: before publishing, verifies the tag matches `pyproject.toml` and `reponeedle.__version__`, runs the full test suite and the strict MCP/security suites, and checks the built artifact versions.

## Documentation and evaluation
- README restructured with a quickstart, a release-status table and clear separation of benchmark kinds.
- Historical ARB v2 results remain as published, now labelled with their engine provenance (commit `8e00425`, 2026-10-28). Current-engine official-harness results, a supplemental whole-file evaluation, and experimental studies are reported separately (`docs/BENCHMARK_CONFIGURATION.md`, `reports/experimental/`). Experimental results are not official ARB scores.
- Corrected earlier inaccurate claims (synthetic "100% abstention accuracy", "calibrated abstention", "100% test coverage", threshold and score ranges).

## Known limitations
- Abstention heuristic is experimental and uncalibrated; out-of-scope queries are not detected by default.
- `comment2context` deep recall remains below BM25 on matched whole-file input (supplemental evaluation). The opt-in documentation filter and the investigated lexical changes were **not validated** and are unchanged.
- No persistent index cache, no live filesystem updates, no HTTP/SSE MCP transport, no AST block slicing.
- Automatic task routing agrees with ARB task labels on 36% of queries; benchmark results pass task labels explicitly.
- See `KNOWN_LIMITATIONS.md`.
