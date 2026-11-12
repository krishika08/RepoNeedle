# Changelog

All notable changes to RepoNeedle are documented here. Versions follow [Semantic Versioning](https://semver.org/).

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
